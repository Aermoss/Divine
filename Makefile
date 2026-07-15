LLVM_PATH = "C:\Program Files\LLVM\lib"
VCPKG_PATH = "C:\vcpkg\installed\x64-windows\lib"

default: build

bin/zirconc2.exe: $(wildcard src/*.zir)
	bin/zirconc.exe src/Main.zir -o $@ -L$(LLVM_PATH) -lLLVM-C -lDbgHelp -g -v

bin/zircraft.exe: Zircraft.zir
	bin/zirconc.exe $< -o $@ -Llib -L$(VCPKG_PATH) -lglfw3dll -lstb_image -lucrt -lmsvcrt -lvcruntime -ldwmapi -g -v

bin/zirgen.exe: Zirgen.zir
	bin/zirconc.exe $< -o $@ -L$(LLVM_PATH) -llibclang -lDbgHelp -g -v

build: bin/zirconc2.exe
build-zircraft: bin/zircraft.exe
build-zirgen: bin/zirgen.exe

run-zircraft: bin/zircraft.exe
	$<

run-zirgen: bin/zirgen.exe
	$<

bootstrap: bin/zirconc2.exe
	copy /Y bin\zirconc2.exe bin\zirconc.exe
	del /Q bin\zirconc2.*

bin/Test.exe: bin/zirconc2.exe examples/Test.zir
	$^ -o $@ -g -v

test: bin/Test.exe
	$<

bin/Count.exe: bin/zirconc2.exe scripts/Count.zir
	$^ -o $@ -g -v

count: bin/Count.exe
	$<

clean:
	del /Q bin\zirconc2.* bin\zircraft.* bin\zirgen.* bin\Count.* bin\Test.*
