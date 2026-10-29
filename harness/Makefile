# Scripted input plugin for the harness (mupen64plus headers from Homebrew). The dylibs go to local/bin/
# (SOTE_LOCAL moves local/, as paths.py).
M64INC ?= /opt/homebrew/opt/mupen64plus/include/mupen64plus
LOCAL := $(or $(SOTE_LOCAL),../local)
BIN := $(LOCAL)/bin
RUN := $(LOCAL)/run

all: $(BIN)/input_script.dylib $(BIN)/audio_dump.dylib

$(BIN)/input_script.dylib: input_script.c
	mkdir -p $(BIN)
	clang -O2 -shared -fPIC -I$(M64INC) $< -o $@

# Audio plugin that writes the game's sound to a raw PCM file (AUDIOPLUGIN=$PWD/../local/bin/audio_dump.dylib).
$(BIN)/audio_dump.dylib: audio_dump.c
	mkdir -p $(BIN)
	clang -O2 -shared -fPIC -I$(M64INC) $< -o $@

# Leftovers of runs: per-run config/EEPROM dirs of killed runs, old EEPROM dirs. Keeps shots and logs.
clean:
	rm -rf $(RUN)/cfg $(RUN)/saves $(RUN)/states/_load.st

# Every recorded screenshot (video takes too: compose first).
clean-shots:
	rm -rf $(RUN)/shots
