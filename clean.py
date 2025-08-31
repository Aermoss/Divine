import sys, os

def main(argv: list[str]) -> int:
    if os.path.exists("__pycache__"):
        for i in os.listdir("__pycache__"):
            os.remove(os.path.join("__pycache__", i))

        os.rmdir("__pycache__")

    for i in os.listdir():
        if os.path.splitext(i)[1] in [".ilk", ".pdb", ".exe", ".llvm", ".json"]:
            os.remove(i)

    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))