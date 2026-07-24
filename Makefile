LLVM_PATH := C:\Program Files\LLVM
VCPKG_PATH := C:\vcpkg\installed\x64-windows

default: build

bin/zirconc2.exe: transpile-llvm $(wildcard src/*.zir) $(wildcard include/vendor/llvm-c/*.zir)
	bin/zirconc.exe src/Main.zir -o $@ -L"$(LLVM_PATH)\lib" -lLLVM-C -lDbgHelp -g -v

bin/zircraft.exe: bin/zirconc2.exe Zircraft.zir
	$^ -o $@ -Llib -L"$(VCPKG_PATH)\lib" -lglfw3dll -lstb_image -lucrt -lmsvcrt -lvcruntime -ldwmapi -g -v

bin/zirgen.exe: Zirgen.zir
	bin/zirconc.exe $^ -o $@ -L"$(LLVM_PATH)\lib" -llibclang -lDbgHelp -g -v

build: bin/zirconc2.exe
build-zircraft: bin/zircraft.exe
build-zirgen: bin/zirgen.exe

run-zircraft: bin/zircraft.exe
	$<

transpile-llvm: bin/zirgen.exe
	$< "$(LLVM_PATH)\include\llvm-c" -I"$(LLVM_PATH)\include"

transpile-clang: bin/zirgen.exe
	$< "$(LLVM_PATH)\include\clang-c" -I"$(LLVM_PATH)\include"

transpile-vulkan: bin/zirgen.exe
	$< "$(VK_SDK_PATH)\Include\vulkan" -I"$(VK_SDK_PATH)\Include"

transpile-glfw: bin/zirgen.exe
	$< "$(VCPKG_PATH)\include\GLFW" -I"$(VCPKG_PATH)\include"

bootstrap: bin/zirconc2.exe
	copy /Y bin\zirconc2.exe bin\zirconc.exe
	del /Q bin\zirconc2.*

restore:
	git restore bin/zirconc.exe

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
