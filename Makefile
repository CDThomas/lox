# Makefile based on: https://github.com/munificent/craftinginterpreters/blob/3e5f0fa6636b68eddfe4dc0173af95130403f961/Makefile

BUILD_DIR := build

default: clox

# Compile a debug build of clox.
debug:
	@ $(MAKE) -f util/c.make NAME=cloxd MODE=debug SOURCE_DIR=src

# Compile the C interpreter.
clox:
	@ $(MAKE) -f util/c.make NAME=clox MODE=release SOURCE_DIR=src
	@ cp build/clox clox # For convenience, copy the interpreter to the top level.

# Remove all build outputs and intermediate files.
clean:
	rm -rf $(BUILD_DIR)

.PHONY: clean clox debug