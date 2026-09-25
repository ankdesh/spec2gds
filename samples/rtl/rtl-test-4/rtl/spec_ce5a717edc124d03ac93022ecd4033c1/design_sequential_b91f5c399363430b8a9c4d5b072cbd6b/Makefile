VERILATOR ?= verilator
TOP_MODULE := sequential_top

.PHONY: check-verilator lint

check-verilator:
	@command -v $(VERILATOR) >/dev/null 2>&1 || { echo "Verilator 5.x is required"; exit 1; }
	@$(VERILATOR) --version | grep -Eq '^Verilator 5\.' || { echo "Verilator 5.x is required"; exit 1; }

lint: check-verilator
	$(VERILATOR) --lint-only --language 1800-2017 -Wall -Wno-PINCONNECTEMPTY --top-module $(TOP_MODULE) -F rtl/files.f
