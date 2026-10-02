// A deliberately small native SystemC emitter for the verified HW/Comb/Seq IR
// produced by the pinned circt-verilog frontend. Unsupported operations fail.

#include "circt/Dialect/Comb/CombDialect.h"
#include "circt/Dialect/HW/HWDialect.h"
#include "circt/Dialect/HW/HWOps.h"
#include "circt/Dialect/Seq/SeqDialect.h"
#include "mlir/IR/BuiltinOps.h"
#include "mlir/IR/MLIRContext.h"
#include "mlir/Parser/Parser.h"
#include "llvm/ADT/DenseMap.h"
#include "llvm/ADT/DenseSet.h"
#include "llvm/Support/raw_ostream.h"

#include <algorithm>
#include <cctype>
#include <fstream>
#include <functional>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

using namespace mlir;

namespace {

std::string str(llvm::StringRef value) { return value.str(); }

std::string safeName(llvm::StringRef raw) {
  std::string result;
  for (char ch : raw) {
    if (std::isalnum(static_cast<unsigned char>(ch)) || ch == '_')
      result += ch;
    else
      result += '_';
  }
  if (result.empty() || std::isdigit(static_cast<unsigned char>(result[0])))
    result.insert(0, "n_");
  return result;
}

// This emitter accepts integer IR only within its declared two-state width
// profile. Parsing registered dialects does not make every operation supported.
unsigned width(Type type) {
  auto integer = llvm::dyn_cast<IntegerType>(type);
  if (!integer || integer.getWidth() < 1 || integer.getWidth() > 64)
    throw std::runtime_error("Only 1-64 bit integer values are supported");
  return integer.getWidth();
}

std::string cppType(unsigned bits) {
  return bits == 1 ? "bool" : "sc_dt::sc_uint<" + std::to_string(bits) + ">";
}

// Each expanded IR value is converted to its destination representation. Note
// that bool performs nonzero conversion, not modulo-two truncation: one-bit
// arithmetic still needs a semantic correction and native regression coverage.
std::string castValue(unsigned bits, const std::string &expression) {
  return cppType(bits) + "(" + expression + ")";
}

std::string opName(Operation *op) { return str(op->getName().getStringRef()); }

std::string opLocation(Operation *op) {
  std::string rendered;
  llvm::raw_string_ostream stream(rendered);
  op->getLoc().print(stream);
  return rendered;
}

std::string moduleName(circt::hw::HWModuleOp module) {
  return str(module.getSymName());
}

struct Port {
  std::string name;
  unsigned bits;
  bool input;
  unsigned argNum;
};

struct Instance {
  Operation *op;
  std::string field;
  std::string sourceName;
  std::string childName;
  std::vector<std::string> inputSignals;
  std::vector<std::string> outputSignals;
  std::vector<std::string> inputNames;
  std::vector<std::string> outputNames;
};

// Validate the module vocabulary before printing a header. Keep value maps for
// ports, registers and child outputs: these are SystemC signal reads and terminate
// expression expansion; remaining combinational IR is expanded recursively.
class ModuleEmitter {
public:
  explicit ModuleEmitter(circt::hw::HWModuleOp module) : module(module) {
    if (!module.getParameters().empty())
      throw std::runtime_error("Parameterized modules are unsupported: " + moduleName(module));
    for (const auto &port : module.getPortList()) {
      if (port.isInOut())
        throw std::runtime_error("Inout ports are unsupported: " + moduleName(module));
      auto name = str(port.getName());
      if (safeName(name) != name)
        throw std::runtime_error("Port cannot be represented as a C++ name: " + name);
      Port value{name, width(port.type), port.isInput(),
                 static_cast<unsigned>(port.argNum)};
      if (value.input)
        inputs.push_back(value);
      else
        outputs.push_back(value);
    }
    auto *body = module.getBodyBlock();
    for (size_t i = 0; i < inputs.size(); ++i)
      portValues[body->getArgument(i)] = inputs[i].name + ".read()";
    for (Operation &op : *body) {
      auto name = opName(&op);
      if (name == "seq.firreg" || name == "seq.compreg") {
        if (op.getNumResults() != 1 || op.getNumOperands() < 2 || op.getNumOperands() > 4)
          throw std::runtime_error("Unsupported register shape in " + moduleName(module));
        width(op.getResult(0).getType());
        regs.push_back(&op);
        regSignals[op.getResult(0)] = "state_" + std::to_string(regs.size() - 1);
      } else if (name == "hw.instance") {
        addInstance(&op);
      } else if (name == "hw.output") {
        output = &op;
      } else if (name != "hw.constant" && name != "seq.to_clock" &&
                 name != "comb.and" && name != "comb.or" && name != "comb.xor" &&
                 name != "comb.add" && name != "comb.sub" && name != "comb.mul" &&
                 name != "comb.mux" && name != "comb.icmp" && name != "comb.shl" &&
                 name != "comb.shru" && name != "comb.concat" &&
                 name != "comb.extract" && name != "comb.replicate") {
        throw std::runtime_error("Unsupported CIRCT operation " + name + " in " +
                                 moduleName(module) + " at " + opLocation(&op));
      }
    }
    if (!output || output->getNumOperands() != outputs.size())
      throw std::runtime_error("Module outputs are inconsistent: " + moduleName(module));
  }

  std::vector<std::string> dependencies() const {
    std::vector<std::string> result;
    for (const auto &instance : instances)
      result.push_back(instance.childName);
    return result;
  }

  std::string emit() {
    std::ostringstream out;
    auto name = moduleName(module);
    out << "SC_MODULE(" << name << ") {\n";
    for (const auto &port : inputs)
      out << "  sc_core::sc_in<" << cppType(port.bits) << "> " << port.name << ";\n";
    for (const auto &port : outputs)
      out << "  sc_core::sc_out<" << cppType(port.bits) << "> " << port.name << ";\n";
    for (size_t i = 0; i < regs.size(); ++i)
      out << "  sc_core::sc_signal<" << cppType(width(regs[i]->getResult(0).getType()))
          << "> state_" << i << ";\n";
    for (const auto &instance : instances) {
      out << "  " << instance.childName << " " << instance.field << ";\n";
      for (size_t i = 0; i < instance.inputSignals.size(); ++i)
        out << "  sc_core::sc_signal<" << cppType(width(instance.op->getOperand(i).getType()))
            << "> " << instance.inputSignals[i] << ";\n";
      for (size_t i = 0; i < instance.outputSignals.size(); ++i)
        out << "  sc_core::sc_signal<" << cppType(width(instance.op->getResult(i).getType()))
            << "> " << instance.outputSignals[i] << ";\n";
    }
    out << "\n";
    emitCombMethod(out);
    for (size_t i = 0; i < regs.size(); ++i)
      emitRegisterMethod(out, i);
    emitConstructor(out);
    out << "};\n\n";
    return out.str();
  }

private:
  circt::hw::HWModuleOp module;
  std::vector<Port> inputs;
  std::vector<Port> outputs;
  std::vector<Operation *> regs;
  std::vector<Instance> instances;
  Operation *output = nullptr;
  llvm::DenseMap<Value, std::string> portValues;
  llvm::DenseMap<Value, std::string> regSignals;
  llvm::DenseMap<Value, std::string> instanceValues;

  // Child port names come from CIRCT attributes, while generated member/signal
  // names use stable local indices. Keep those identities separate during binding.
  void addInstance(Operation *op) {
    auto child = op->getAttrOfType<FlatSymbolRefAttr>("moduleName");
    auto instanceName = op->getAttrOfType<StringAttr>("instanceName");
    auto argNames = op->getAttrOfType<ArrayAttr>("argNames");
    auto resultNames = op->getAttrOfType<ArrayAttr>("resultNames");
    if (!child || !instanceName || !argNames || !resultNames ||
        argNames.size() != op->getNumOperands() || resultNames.size() != op->getNumResults())
      throw std::runtime_error("Malformed hw.instance in " + moduleName(module));
    unsigned index = instances.size();
    Instance instance{op, "child_" + std::to_string(index), str(instanceName.getValue()),
                      str(child.getValue()), {}, {}, {}, {}};
    for (unsigned i = 0; i < op->getNumOperands(); ++i) {
      instance.inputSignals.push_back("child_" + std::to_string(index) + "_in_" +
                                      std::to_string(i));
      instance.inputNames.push_back(str(llvm::cast<StringAttr>(argNames[i]).getValue()));
    }
    for (unsigned i = 0; i < op->getNumResults(); ++i) {
      auto signal = "child_" + std::to_string(index) + "_out_" + std::to_string(i);
      instance.outputSignals.push_back(signal);
      instance.outputNames.push_back(str(llvm::cast<StringAttr>(resultNames[i]).getValue()));
      instanceValues[op->getResult(i)] = signal;
    }
    instances.push_back(std::move(instance));
  }

  // Detect recursion on the current expansion path, not with a global visited
  // set: shared DAG values may be reused, but a combinational feedback loop fails.
  // Register signal reads above the recursive branch preserve legal state feedback.
  std::string expression(Value value, llvm::DenseSet<Value> &active) {
    if (auto it = portValues.find(value); it != portValues.end())
      return it->second;
    if (auto it = regSignals.find(value); it != regSignals.end())
      return it->second + ".read()";
    if (auto it = instanceValues.find(value); it != instanceValues.end())
      return it->second + ".read()";
    if (!active.insert(value).second)
      throw std::runtime_error("Combinational cycle in " + moduleName(module));
    Operation *op = value.getDefiningOp();
    if (!op)
      throw std::runtime_error("Unknown value origin in " + moduleName(module));
    auto name = opName(op);
    std::string result;
    auto operand = [&](unsigned i) { return expression(op->getOperand(i), active); };
    if (name == "hw.constant") {
      auto literal = op->getAttrOfType<IntegerAttr>("value");
      if (!literal)
        throw std::runtime_error("Non-integer constant in " + moduleName(module));
      unsigned bits = width(value.getType());
      auto number = literal.getValue().getZExtValue();
      result = bits == 1 ? (number ? "true" : "false")
                         : castValue(bits, std::to_string(number) + "ULL");
    } else if (name == "seq.to_clock") {
      result = operand(0);
    } else if (name == "comb.mux") {
      result = "(" + operand(0) + " ? " + operand(1) + " : " + operand(2) + ")";
    } else if (name == "comb.and" || name == "comb.or" || name == "comb.xor" ||
               name == "comb.add" || name == "comb.sub" || name == "comb.mul") {
      const char *symbol = name == "comb.and" ? " & " : name == "comb.or" ? " | " :
                           name == "comb.xor" ? " ^ " : name == "comb.add" ? " + " :
                           name == "comb.sub" ? " - " : " * ";
      result = "(" + operand(0);
      for (unsigned i = 1; i < op->getNumOperands(); ++i)
        result += symbol + operand(i);
      result += ")";
    } else if (name == "comb.extract") {
      auto lowBit = op->getAttrOfType<IntegerAttr>("lowBit");
      if (!lowBit || op->getNumOperands() != 1)
        throw std::runtime_error("Malformed comb.extract in " + moduleName(module));
      result = "(" + operand(0) + " >> " +
               std::to_string(lowBit.getValue().getZExtValue()) + ")";
    } else if (name == "comb.concat" || name == "comb.replicate") {
      if (op->getNumOperands() == 0)
        throw std::runtime_error("Empty concatenation in " + moduleName(module));
      unsigned resultBits = width(value.getType());
      result = cppType(resultBits) + "(0)";
      unsigned count = name == "comb.replicate"
                           ? resultBits / width(op->getOperand(0).getType())
                           : op->getNumOperands();
      if (name == "comb.replicate" &&
          count * width(op->getOperand(0).getType()) != resultBits)
        throw std::runtime_error("Malformed comb.replicate in " + moduleName(module));
      for (unsigned i = 0; i < count; ++i) {
        unsigned operandIndex = name == "comb.replicate" ? 0 : i;
        unsigned operandBits = width(op->getOperand(operandIndex).getType());
        result = "((" + result + " << " + std::to_string(operandBits) + ") | " +
                 castValue(resultBits, operand(operandIndex)) + ")";
      }
    } else if (name == "comb.shl" || name == "comb.shru") {
      result = "(" + operand(0) + (name == "comb.shl" ? " << " : " >> ") +
               operand(1) + ")";
    } else if (name == "comb.icmp") {
      auto predicate = op->getAttr("predicate");
      std::string rendered;
      if (predicate) {
        llvm::raw_string_ostream stream(rendered);
        predicate.print(stream);
      }
      const char *symbol = rendered.find("eq") != std::string::npos ? " == " :
                           rendered.find("ne") != std::string::npos ? " != " :
                           rendered.find("ugt") != std::string::npos ? " > " :
                           rendered.find("uge") != std::string::npos ? " >= " :
                           rendered.find("ult") != std::string::npos ? " < " :
                           rendered.find("ule") != std::string::npos ? " <= " : nullptr;
      if (!symbol)
        throw std::runtime_error("Unsupported comparison predicate in " + moduleName(module));
      result = "(" + operand(0) + symbol + operand(1) + ")";
    } else {
      throw std::runtime_error("Unsupported expression operation " + name + " in " +
                               moduleName(module) + " at " + opLocation(op));
    }
    active.erase(value);
    return castValue(width(value.getType()), result);
  }

  std::string expression(Value value) {
    llvm::DenseSet<Value> active;
    return expression(value, active);
  }

  void emitCombMethod(std::ostringstream &out) {
    out << "  void update_comb() {\n";
    for (const auto &instance : instances)
      for (size_t i = 0; i < instance.inputSignals.size(); ++i)
        out << "    " << instance.inputSignals[i] << ".write("
            << expression(instance.op->getOperand(i)) << ");\n";
    for (size_t i = 0; i < outputs.size(); ++i)
      out << "    " << outputs[i].name << ".write("
          << expression(output->getOperand(i)) << ");\n";
    out << "  }\n\n";
  }

  // Register scheduling supports direct input clocks only. Accepting arbitrary
  // computed clock expressions here would require a different sensitivity model.
  Value clockSource(Operation *reg) {
    auto *clockOp = reg->getOperand(1).getDefiningOp();
    if (!clockOp || opName(clockOp) != "seq.to_clock" ||
        clockOp->getNumOperands() != 1)
      throw std::runtime_error("Only direct rising-edge input clocks are supported");
    auto source = clockOp->getOperand(0);
    if (!portValues.count(source))
      throw std::runtime_error("Only input-port clocks are supported");
    return source;
  }

  // Recover the physical reset input and assertion edge from CIRCT's direct or
  // XOR-inverted reset. Do not infer a sensitivity edge from an arbitrary cone.
  std::pair<Value, bool> resetSource(Operation *reg) {
    if (reg->getNumOperands() < 4)
      return {Value(), false};
    Value reset = reg->getOperand(2);
    if (portValues.count(reset))
      return {reset, true};
    Operation *def = reset.getDefiningOp();
    if (def && opName(def) == "comb.xor" && def->getNumOperands() == 2) {
      for (unsigned i = 0; i < 2; ++i) {
        Value candidate = def->getOperand(i);
        Value other = def->getOperand(1 - i);
        Operation *constant = other.getDefiningOp();
        if (portValues.count(candidate) && constant &&
            opName(constant) == "hw.constant") {
          auto attr = constant->getAttrOfType<IntegerAttr>("value");
          if (attr && attr.getValue().getZExtValue() == 1)
            return {candidate, false};
        }
      }
    }
    throw std::runtime_error("Reset must be a direct input or its inversion");
  }

  // sc_signal::write defers updates to SystemC's update phase. Separate register
  // methods therefore read the old state on an edge rather than sequentially
  // exposing a prior method's newly computed register value.
  void emitRegisterMethod(std::ostringstream &out, size_t index) {
    Operation *reg = regs[index];
    (void)clockSource(reg);
    out << "  void update_state_" << index << "() {\n";
    if (reg->getNumOperands() == 4)
      out << "    if (" << expression(reg->getOperand(2)) << ")\n"
          << "      state_" << index << ".write("
          << expression(reg->getOperand(3)) << ");\n"
          << "    else\n      state_" << index << ".write("
          << expression(reg->getOperand(0)) << ");\n";
    else
      out << "    state_" << index << ".write("
          << expression(reg->getOperand(0)) << ");\n";
    out << "  }\n\n";
  }

  void emitConstructor(std::ostringstream &out) {
    out << "  SC_CTOR(" << moduleName(module) << ")";
    bool first = true;
    auto initializer = [&](const std::string &field, const std::string &name) {
      out << (first ? " : " : ", ") << field << "(\"" << name << "\")";
      first = false;
    };
    for (const auto &port : inputs)
      initializer(port.name, port.name);
    for (const auto &port : outputs)
      initializer(port.name, port.name);
    for (size_t i = 0; i < regs.size(); ++i)
      initializer("state_" + std::to_string(i), "state_" + std::to_string(i));
    for (const auto &instance : instances) {
      initializer(instance.field, instance.sourceName);
      for (const auto &signal : instance.inputSignals)
        initializer(signal, signal);
      for (const auto &signal : instance.outputSignals)
        initializer(signal, signal);
    }
    out << " {\n";
    for (const auto &instance : instances) {
      for (size_t i = 0; i < instance.inputSignals.size(); ++i)
        out << "    " << instance.field << "." << instance.inputNames[i] << "("
            << instance.inputSignals[i] << ");\n";
      for (size_t i = 0; i < instance.outputSignals.size(); ++i)
        out << "    " << instance.field << "." << instance.outputNames[i] << "("
            << instance.outputSignals[i] << ");\n";
    }
    out << "    SC_METHOD(update_comb);\n";
    for (const auto &port : inputs)
      out << "    sensitive << " << port.name << ";\n";
    for (size_t i = 0; i < regs.size(); ++i)
      out << "    sensitive << state_" << i << ";\n";
    for (const auto &instance : instances)
      for (const auto &signal : instance.outputSignals)
        out << "    sensitive << " << signal << ";\n";
    for (size_t i = 0; i < regs.size(); ++i) {
      Operation *reg = regs[i];
      Value clock = clockSource(reg);
      out << "    SC_METHOD(update_state_" << i << ");\n";
      std::string clockName = portValues[clock];
      clockName.erase(clockName.size() - std::string(".read()").size());
      out << "    sensitive << " << clockName << ".pos();\n";
      if (reg->hasAttr("isAsync")) {
        auto [source, activeHigh] = resetSource(reg);
        std::string resetName = portValues[source];
        resetName.erase(resetName.size() - std::string(".read()").size());
        out << "    sensitive << " << resetName
            << (activeHigh ? ".pos();\n" : ".neg();\n");
      }
      // State methods run on clock/reset events, not as a time-zero assignment.
      // Initial signal values are outside the documented pre-reset equivalence scope.
      out << "    dont_initialize();\n";
    }
    out << "  }\n";
  }
};

std::string emitAll(ModuleOp root, llvm::StringRef top) {
  std::unordered_map<std::string, std::unique_ptr<ModuleEmitter>> modules;
  for (Operation &op : root.getBody()->getOperations())
    if (!llvm::isa<circt::hw::HWModuleOp>(op))
      throw std::runtime_error("Unsupported top-level CIRCT operation " +
                               opName(&op) + " at " + opLocation(&op));
  for (auto module : root.getOps<circt::hw::HWModuleOp>()) {
    auto name = moduleName(module);
    if (modules.count(name))
      throw std::runtime_error("Duplicate hardware module " + name);
    modules[name] = std::make_unique<ModuleEmitter>(module);
  }
  if (!modules.count(str(top)))
    throw std::runtime_error("Selected top module is missing from CIRCT IR");
  std::ostringstream output;
  output << "#pragma once\n#include <systemc>\n\n";
  std::unordered_map<std::string, unsigned> state;
  // Three-state DFS emits reachable children before parents, once per module.
  // The active state detects instantiation cycles; completed modules are reused.
  std::function<void(const std::string &)> visit = [&](const std::string &name) {
    if (!modules.count(name))
      throw std::runtime_error("Instance references unknown module " + name);
    if (state[name] == 2)
      return;
    if (state[name] == 1)
      throw std::runtime_error("Module instantiation cycle at " + name);
    state[name] = 1;
    for (const auto &child : modules[name]->dependencies())
      visit(child);
    output << modules[name]->emit();
    state[name] = 2;
  };
  visit(str(top));
  return output.str();
}

} // namespace

int main(int argc, char **argv) {
  std::string input, output, top;
  for (int i = 1; i < argc; ++i) {
    std::string arg(argv[i]);
    if (arg == "--version") {
      llvm::outs() << "spec2gds-systemc-emit 1.0.0\n";
      return 0;
    }
    if (i + 1 >= argc) {
      llvm::errs() << "Missing argument value for " << arg << "\n";
      return 2;
    }
    if (arg == "--input")
      input = argv[++i];
    else if (arg == "--output")
      output = argv[++i];
    else if (arg == "--top")
      top = argv[++i];
    else {
      llvm::errs() << "Unknown argument " << arg << "\n";
      return 2;
    }
  }
  if (input.empty() || output.empty() || top.empty()) {
    llvm::errs() << "Usage: spec2gds-systemc-emit --input IR --output HEADER --top MODULE\n";
    return 2;
  }
  try {
    MLIRContext context;
    // Permit parsing unknown dialect syntax so our explicit vocabulary checks
    // can report an unsupported operation instead of silently skipping it.
    context.allowUnregisteredDialects();
    context.getOrLoadDialect<circt::hw::HWDialect>();
    context.getOrLoadDialect<circt::comb::CombDialect>();
    context.getOrLoadDialect<circt::seq::SeqDialect>();
    auto module = parseSourceFile<ModuleOp>(input, &context);
    if (!module)
      return 1;
    // Build the full header before opening output: unsupported semantics should
    // not leave a partially emitted header. Filesystem write failure is separate.
    auto text = emitAll(*module, top);
    std::ofstream file(output, std::ios::binary);
    if (!file)
      throw std::runtime_error("Cannot open output header " + output);
    file << text;
    return file ? 0 : 1;
  } catch (const std::exception &error) {
    llvm::errs() << "SystemC emission failed: " << error.what() << "\n";
    return 1;
  }
}
