import spec2gds.spec.odt_container.editor_core.document as document
import spec2gds.spec.odt_container.editor_core.ipxact_view as ipxact_view
import spec2gds.spec.odt_container.editor_core.session as session

Diagnostic = document.Diagnostic
DocumentLink = document.DocumentLink
SemanticBlock = document.SemanticBlock
SectionVariant = document.SectionVariant
SectionVariantGroup = document.SectionVariantGroup
SemanticDocument = document.SemanticDocument
parse_content_xml = document.parse_content_xml
apply_text_edits_to_content_xml = document.apply_text_edits_to_content_xml

IpxactComponentSummary = ipxact_view.IpxactComponentSummary
IpxactInterfaceSummary = ipxact_view.IpxactInterfaceSummary
extract_ipxact_summary = ipxact_view.extract_ipxact_summary

EditorSnapshot = session.EditorSnapshot
EditorSession = session.EditorSession
