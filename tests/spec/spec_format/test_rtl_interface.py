"""Exact bounds, parameter elaboration, and complete Component acceptance."""
import importlib.util
import shutil
import subprocess
from pathlib import Path

import pytest

from spec2gds.spec.spec_format.rtl_interface import resolve_interface, split_range
from spec2gds.spec.spec_format.archive import SpecPackage
from spec2gds.spec.spec_format.assistant import SpecChangeProposal, preview_assistant_proposal
from spec2gds.spec.spec_format.ir import SpecRevision
from spec2gds.spec.activities.rtl.codegen import generate_project
from spec2gds.spec.activities.view import SpecAccess


def port(name="A", value="4:1", direction="in"):
    return {"name": name, "direction": direction, "range": value, "description": "Input operand"}


@pytest.mark.parametrize("source,left,right,width", [("4:1",4,1,4),("0:3",0,3,4),("-1:-4",-1,-4,4),("4:4",4,4,1),(None,None,None,1),("0",0,0,1)])
def test_literal_bounds_need_no_compiler(monkeypatch, source, left, right, width):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("Literal bounds must not invoke a compiler"))
    result = resolve_interface([port(value=source)])
    assert result["ports"] == [{"name":"A", "range":source, "left":left, "right":right, "width":width}]
    assert not result["compiler_required"]


@pytest.mark.parametrize("expression", ["(USE ? WIDTH:2)-1:0", "(WIDTH**2)-1:1", "$clog2(WIDTH):0", "calc(WIDTH)-1:0", "WIDTH[2:0]", "-WIDTH:-WIDTH"])
def test_full_constant_expression_elaboration(expression):
    assert shutil.which("verilator"), "Verilator is required"
    parameters=[{"name":"WIDTH","rtl_type":"int unsigned","value":"4"},{"name":"USE","rtl_type":"bit","value":"1"}]
    context="function automatic int calc(input int n); return 1 << $clog2(n); endfunction"
    result=resolve_interface([port(value=expression)],parameters,context)
    assert result["status"]=="resolved",result
    assert result["parameter_values"]=={"WIDTH":4,"USE":1}
    bounds=result["ports"][0]
    assert bounds["width"]==abs(bounds["left"]-bounds["right"])+1
    assert bounds["range"]==expression
    changed=resolve_interface([port(value=expression)],parameters,context,{"WIDTH":"8"})
    assert changed["status"]=="resolved",changed
    assert (changed["ports"][0]["left"],changed["ports"][0]["right"]) != (bounds["left"],bounds["right"])


def test_missing_dependencies_and_defaults_do_not_invent_widths(monkeypatch):
    result=resolve_interface([port(value="MISSING-1:0")])
    assert result["status"]=="unresolved" and not result["ports"]
    assert any("MISSING" in diagnostic["message"] for diagnostic in result["diagnostics"])
    with pytest.raises(ValueError,match="WIDTH.*default"):
        resolve_interface([port(value="WIDTH-1:0")],[{"name":"WIDTH","value":""}])
    monkeypatch.setattr(shutil,"which",lambda name:None)
    result=resolve_interface([port(value="WIDTH-1:0")],[{"name":"WIDTH","value":"4"}])
    assert result["status"]=="unresolved" and not result["ports"]


def test_parameter_dependencies_signed_defaults_and_override_propagation():
    parameters = [
        {"name": "BASE", "rtl_type": "int signed", "value": "-2"},
        {"name": "WIDTH", "rtl_type": "int unsigned", "value": "4"},
        {"name": "LAST", "rtl_type": "int signed", "value": "BASE+WIDTH-1"},
    ]
    result = resolve_interface([port(value="BASE:LAST")], parameters)
    assert result["status"] == "resolved", result
    assert result["parameter_values"] == {"BASE": -2, "WIDTH": 4, "LAST": 1}
    assert result["ports"][0] == {"name": "A", "range": "BASE:LAST", "left": -2, "right": 1, "width": 4}
    changed = resolve_interface([port(value="BASE:LAST")], parameters, overrides={"WIDTH": "8"})
    assert changed["status"] == "resolved", changed
    assert changed["parameter_values"] == {"BASE": -2, "WIDTH": 8, "LAST": 5}
    assert changed["ports"][0]["width"] == 8


def component_revision(source_range, body, parameters=()):
    revision=SpecRevision.from_package(SpecPackage.create("interface-spec"))
    reference={"document_id":revision.document_id,"entity_kind":"component","entity_id":"leaf"}
    ports=[port("a",source_range),port("b",source_range),port("sum",source_range,"out")]
    operations=[{"operation_id":"create","type":"create_entity","kind":"component","name":"range_adder","entity_id":"leaf","ports":[{**p,"family":"wire"} for p in ports],"systemverilog":body}]
    operations += [{"operation_id":f"p{i}","type":"upsert_parameter","entity":reference,"parameter":p} for i,p in enumerate(parameters)]
    proposal=SpecChangeProposal(document_id=revision.document_id,scope="document",proposal_id="range-proposal",base_source_revision_hash=revision.source_revision_hash,title="Add range adder",summary="Exact interface",rationale="Preserve supplied ranges",operations=operations)
    preview=preview_assistant_proposal(revision,proposal)
    assert preview["status"]=="valid",preview
    candidate=preview["_revision"]
    assert candidate.components[0].ports[0].width==f"[{source_range}]"
    return candidate


@pytest.mark.parametrize("source_range,parameters", [("4:1",[]),("WIDTH:1",[{"name":"WIDTH","rtl_type":"int unsigned","value":"4","description":"Operand upper bound"}])])
def test_saved_interface_generated_rtl_and_simulation_agree(tmp_path,source_range,parameters):
    revision=component_revision(source_range,"assign sum = a + b;",parameters)
    component=revision.components[0]
    project=generate_project(SpecAccess(revision,component.ref),component.ref)
    source=project.files["rtl/components/range_adder.sv"].decode()
    assert f"[{source_range}] a" in source
    if parameters:
        assert "parameter int unsigned WIDTH = 4" in source
        assert "[WIDTH:1] sum" in source
    for path,data in project.files.items():
        destination=tmp_path/path;destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(data)
    bench=tmp_path/'bench.sv'
    bench.write_text('module bench; logic [4:1] a,b,sum; range_adder dut(.*); initial begin a=4\'h5; b=4\'h3; #1; if(sum!==4\'h8) $fatal; $finish; end endmodule\n')
    run=subprocess.run(['verilator','--binary','--timing','-Wno-fatal','--top-module','bench','--Mdir',str(tmp_path/'obj'),str(tmp_path/'rtl/components/range_adder.sv'),str(bench)],capture_output=True,text=True)
    assert run.returncode==0,run.stderr
    assert subprocess.run([str(tmp_path/'obj/Vbench')],capture_output=True).returncode==0
    if parameters:
        lint=subprocess.run(['verilator','--lint-only','-Wno-fatal','--top-module','range_adder','-GWIDTH=8',str(tmp_path/'rtl/components/range_adder.sv')],capture_output=True,text=True)
        assert lint.returncode==0,lint.stderr


def test_label_cleanup_preserves_description_and_other_members(tmp_path, monkeypatch):
    spec=importlib.util.spec_from_file_location("cleanup",Path(__file__).resolve().parents[3]/"scripts/cleanup-port-labels.py")
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    package=SpecPackage.load("samples/minimal/single_component.spec")
    entry=next(entry for entry in package.manifest.documents if entry.kind=="component")
    # Construct an existing archive directly: current writers never author labels.
    import lxml.etree as E
    from spec2gds.spec.spec_format.models import sha256_digest
    root=E.fromstring(package.files[entry.path]);ns={'x':root.tag.split('}')[0][1:]}
    port_node=root.find('x:model/x:ports/x:port',ns)
    label=E.Element(root.tag.split('}')[0]+'}displayName');label.text='Label to discard';port_node.insert(1,label)
    encoded=E.tostring(root);package.files[entry.path]=encoded
    package.manifest=package.manifest.model_copy(update={"documents":[item.model_copy(update={"sha256":sha256_digest(encoded)}) if item==entry else item for item in package.manifest.documents]})
    before=dict(package.files);description=port_node.findtext('x:description',namespaces=ns)
    cleaned,count=module.clean_package(package)
    assert count>=1 and b'Label to discard' not in cleaned.files[entry.path]
    assert E.fromstring(cleaned.files[entry.path]).find('x:model/x:ports/x:port',ns).findtext('x:description',namespaces=ns)==description
    assert all(cleaned.files[path]==data for path,data in before.items() if path!=entry.path)
    assert module.clean_package(cleaned)[1]==0
    # Store cleanup evidence in the scanned checkout, as a developer can do.
    # A rerun must not clean or overwrite the original backup.
    import json, sys
    project = tmp_path / "project"
    (project / "scripts").mkdir(parents=True)
    source = project / "labelled.spec"
    package.save(str(source))
    original = source.read_bytes()
    output = project / "cleanup-evidence"
    monkeypatch.setattr(module, "__file__", str(project / "scripts/cleanup-port-labels.py"))
    monkeypatch.setattr(sys, "argv", ["cleanup-port-labels.py", "--apply", "--output", str(output)])
    assert module.main() == 0
    report = json.loads((output / "report.json").read_text())
    backup = Path(report["files"][0]["backup"])
    assert backup.read_bytes() == original
    assert module.main() == 0
    assert json.loads((output / "report.json").read_text())["files"] == []
    assert backup.read_bytes() == original


def test_carry_lookahead_creation_keeps_four_to_one_bits(tmp_path):
    revision=SpecRevision.from_package(SpecPackage.create("cla-test"))
    ports=[{**port(name,"4:1",direction),"family":"wire"} for name,direction in [("a","in"),("b","in"),("sum","out")]]
    ports += [{**port(name,None,direction),"family":"wire"} for name,direction in [("cin","in"),("p_grp","out"),("g_grp","out"),("cout","out")]]
    body="""logic [4:1] p,g,c;
assign p=a^b; assign g=a&b;
assign c[1]=g[1]|(p[1]&cin);
assign c[2]=g[2]|(p[2]&g[1])|(p[2]&p[1]&cin);
assign c[3]=g[3]|(p[3]&g[2])|(p[3]&p[2]&g[1])|(p[3]&p[2]&p[1]&cin);
assign c[4]=g[4]|(p[4]&g[3])|(p[4]&p[3]&g[2])|(p[4]&p[3]&p[2]&g[1])|(p[4]&p[3]&p[2]&p[1]&cin);
assign sum[1]=p[1]^cin; assign sum[2]=p[2]^c[1]; assign sum[3]=p[3]^c[2]; assign sum[4]=p[4]^c[3];
assign p_grp=&p;
assign g_grp=g[4]|(p[4]&g[3])|(p[4]&p[3]&g[2])|(p[4]&p[3]&p[2]&g[1]);
assign cout=c[4];"""
    proposal=SpecChangeProposal(document_id=revision.document_id,scope="document",proposal_id="cla",base_source_revision_hash=revision.source_revision_hash,title="Add CLA",summary="Preserve interface",rationale="Supplied code",operations=[{"operation_id":"create","type":"create_entity","kind":"component","name":"cla_4bit","entity_id":"cla","ports":ports,"systemverilog":body}])
    rebased_ports = [{**item, "range": "3:0" if item["range"] == "4:1" else item["range"]} for item in ports]
    rebased = proposal.model_copy(update={"operations": [{**proposal.operations[0], "ports": rebased_ports}]})
    bad_preview = preview_assistant_proposal(revision, rebased)
    assert bad_preview["status"] == "valid", bad_preview
    assert "out of range" in str(bad_preview["section_validation"]).lower(), bad_preview
    preview=preview_assistant_proposal(revision,proposal)
    assert preview["status"]=="valid",preview
    assert not any("out of range" in str(item) for item in preview.get("section_validation",[]))
    candidate=preview["_revision"];project=generate_project(SpecAccess(candidate,candidate.components[0].ref),candidate.components[0].ref)
    source=tmp_path/'cla.sv';source.write_bytes(project.files['rtl/components/cla_4bit.sv'])
    bench=tmp_path/'bench.sv';bench.write_text("""module bench;
logic [4:1] a,b,sum; logic cin,p_grp,g_grp,cout;
cla_4bit dut(.*);
initial begin
for (int i=0;i<16;i++) for(int j=0;j<16;j++) for(int k=0;k<2;k++) begin
a=4'(i); b=4'(j); cin=1'(k); #1;
if ({cout,sum} !== 5'(i+j+k)) $fatal;
end
$finish;
end endmodule
""")
    run=subprocess.run(['verilator','--binary','--timing','-Wno-fatal','--top-module','bench','--Mdir',str(tmp_path/'obj'),str(source),str(bench)],capture_output=True,text=True)
    assert run.returncode==0,run.stderr
    assert subprocess.run([str(tmp_path/'obj/Vbench')],capture_output=True).returncode==0


def test_elaboration_endpoint_is_read_only_and_reports_source_bounds():
    from fastapi.testclient import TestClient
    from spec2gds.spec.spec_format.v1_api import create_app
    with TestClient(create_app()) as client:
        response=client.post('/assistant/resolve-interface',json={"ports":[port(value="WIDTH:1")],"parameters":[{"name":"WIDTH","rtl_type":"int unsigned","value":"4"}],"overrides":{"WIDTH":"8"}})
        assert response.status_code==200,response.text
        assert response.json()["ports"]==[{"name":"A","range":"WIDTH:1","left":8,"right":1,"width":8}]
        invalid=client.post('/assistant/resolve-interface',json={"ports":[{**port(),"width":4}]})
        assert invalid.status_code==422
