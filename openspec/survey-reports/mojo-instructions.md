### **Mojo-Readiness Coding Guidelines for AI Agents**

To ensure that the Python code generated for this project is highly compatible with a future migration to Mojo, prioritize the following structural rules and architectural constraints over default Python PEP-8 dynamic conventions.

### **1\. Variables, Type Integrity, and Value Semantics**

* **Enforce Strict Type-Locking:** Always assign explicit type annotations to variables upon their first assignment (e.g., `data_packet: int = 1024`). Do not reassign a variable to a different type later in the scope (e.g., changing an `int` to a `str`).  
* **Implement Explicit Value Copying:** Python uses reference semantics by default, whereas Mojo defaults to value semantics. When sharing list, dictionary, or custom object states across scopes, do not rely on implicit references. Use `copy.copy()` or `copy.deepcopy()` explicitly so changes do not unexpectedly propagate.  
* **Prohibit Global State Mutations:** Avoid the `global` namespace keyword entirely. Avoid file-scope global variables, as they generate compiler warnings. Pass state parameters explicitly through function boundaries or wrap them within class/struct instances.  
* **Isolate Optional types:** When a variable can hold either a value or `None`, explicitly annotate it using `Optional` from the `typing` module to prepare for Mojo's compile-time null-safety checks.

### **2\. Function Design and Argument Conventions**

* **Declare with `def` only:** Do not use `fn` for function declarations, as the `fn` keyword is deprecated.  
* **Enforce Complete Parameter and Return Typing:** Every `def` block must be fully type-annotated. Unannotated parameters default to slow, dynamic dynamic-dispatch wrapper objects in Mojo.  
* **Assume Default Read-Only (Immutable) Parameters:** Treat all incoming function parameters as immutable by default. If an input parameter must be modified locally within the function body, create an explicit local copy immediately:  
* Python

def process\_data(payload: list) \-\> list:  
    \# Create a local mutable copy to mirror Mojo's "read" constraint  
    local\_payload \= copy.copy(payload)   
    local\_payload.append("processed")  
    return local\_payload

*   
*   
* **Ban Comprehensions in Intensive Loops:** Do not use list, dictionary, or set comprehensions. Implement explicit, sequential `for` loops utilizing `list.append()` or `dict.update()` to avoid inline-allocation syntax issues during compiler migration.

### **3\. Object Modeling: Python Classes to Compile-Time Structs**

* **Declare Static Class Fields:** Pre-declare all instance attributes directly inside the class body with type annotations.  
* **Strict Constructor Initialization:** Initialize every class attribute inside the `__init__` constructor. Do not inject dynamic properties onto objects at runtime outside of the constructor.  
* **Ban Class-Level Attribute Initialization:** Do not assign default instance values during class-level field declarations. The only class-level variables allowed are compile-time constants.  
* **Design for Composition (No Concrete Inheritance):** Mojo structs do not support class-based inheritance. Replace traditional polymorphic subclass hierarchies with static trait interfaces by defining abstract behaviors via `typing.Protocol` or `abc.ABC`.  
* **Avoid Recursive Data Types:** Do not nest a class definition directly inside itself (e.g., `class Node: next: Optional[Node]`). Simulate pointer connections using index arrays or flat collections to allow seamless migration to Mojo’s raw pointer arrays (`UnsafePointer`).

### **4\. Exceptional Control Flow & Error Management**

* **Enforce Single-Exception Handling Blocks:** Do not catch multiple distinct exception types in a single `try` block, and avoid consecutive `except` clauses.  
* **Utilize Sequential `try` Structures:** Group different operations that can raise separate exceptions into independent, sequential `try` blocks :  
* Python

\# Mojo-compliant sequential layout  
try:  
    validated\_name \= validate\_user(input\_data)  
except ValidationError as e:  
    handle\_validation\_error(e)

try:  
    file\_handler \= open\_system\_file(config\_path)  
except FileNotFoundError as e:  
    handle\_missing\_file(e)

### **5\. Dependency Imports & Runtime Management**

* **Prohibit "From" Member Imports:** Do not import individual functions or classes directly from a package (e.g., avoid `from numpy import array`). Import the entire module namespace and access members via dot-notation:  
* Python

import numpy as np  
matrix \= np.array(\[1, 2, 3\])  \# Enforces module-variable path routing

* **Declare Strict Environment Bounds:** Manage virtual environments and dependencies using deterministic package managers such as **Pixi** or **uv**. Pin the runtime strictly to a compatible version (e.g., Python 3.11).

### **6\. Test Engineering Design Rules**

* **Enforce Module-Scoped Testing:** Define all unit tests at the module scope. Do not group unit tests inside runner classes (avoid `unittest.TestCase` structures).  
* **Test Discovery Signatures:** Every test must be a standalone function whose name is prefixed with `test_`, takes zero arguments, and returns `None`.  
* **Assert via Exception-Raising Blocks:** Signal test failure by raising standard Python errors. Do not use complex framework assertions; rely on simple conditional checks that throw errors when conditions are unfulfilled. Use context managers to verify expected raising behaviors.

