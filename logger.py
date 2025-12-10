def log(msg):
    print(paint(f"[LOG] {msg}", Color.YELLOW))

def log_info(msg):
    print(paint(f"[INFO] {msg}", Color.BLUE))

def log_err(msg):
    print(paint(f"[ERR] {msg}", Color.RED))

def log_important(msg):
     print(paint(f"[IMPORTANT] {msg}", Color.MAGENTA))

def paint(text, color):
        return f"{color}{text}{Color.RESET}"

class Color:
    RESET  = "\033[0m"
    BLACK  = "\033[30m"
    RED    = "\033[31m"
    GREEN  = "\033[32m"
    YELLOW = "\033[33m"
    BLUE   = "\033[34m"
    MAGENTA= "\033[35m"
    CYAN   = "\033[36m"
    WHITE  = "\033[37m"