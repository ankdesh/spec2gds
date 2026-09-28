cmake_minimum_required(VERSION 3.20)
project(spec2gds_systemc_emitter LANGUAGES CXX)

find_package(LLVM REQUIRED CONFIG)
find_package(MLIR REQUIRED CONFIG)
find_package(CIRCT REQUIRED CONFIG)

add_executable(spec2gds-systemc-emit main.cpp)
target_compile_features(spec2gds-systemc-emit PRIVATE cxx_std_17)
target_include_directories(spec2gds-systemc-emit PRIVATE
  ${LLVM_INCLUDE_DIRS} ${MLIR_INCLUDE_DIRS} ${CIRCT_INCLUDE_DIRS})
target_link_libraries(spec2gds-systemc-emit PRIVATE
  CIRCTHW CIRCTComb CIRCTSeq MLIRParser MLIRIR MLIRSupport)
set_target_properties(spec2gds-systemc-emit PROPERTIES
  INSTALL_RPATH "$ORIGIN/../lib")
install(TARGETS spec2gds-systemc-emit RUNTIME DESTINATION bin)
