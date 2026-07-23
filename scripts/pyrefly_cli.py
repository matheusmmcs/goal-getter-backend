import sys
import subprocess

def main():
    """
    CLI entrypoint for `poetry run pyrefly check`.
    Executes static type checking on the app codebase.
    """
    args = sys.argv[1:]

    # Remove 'check' command if passed, or pass args through
    if args and args[0] == "check":
        extra_args = args[1:]
    elif args and args[0] in ("-h", "--help"):
        print("Pyrefly Static Type Checker (Goal Getter Backend)")
        print("\nUso:")
        print("  poetry run pyrefly check    Executa verificação estática de tipos no projeto")
        print("  poetry run pyrefly --help   Exibe esta ajuda")
        sys.exit(0)
    else:
        extra_args = args

    print("🔍 Executando verificação de tipos estáticos com Pyrefly...")
    cmd = [sys.executable, "-m", "pyright"] + extra_args
    result = subprocess.run(cmd)
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()
