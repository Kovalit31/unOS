#!/usr/bin/env python3
import selectors
import signal
import sys
import os
import shutil
import termios
import time
import pty
from argparse import ArgumentParser

# Versions
MAJOR_VER = 0
MINOR_VER = 1
PATCH_LEVEL = 2
EXTRA = "alpha"
VERSION = ".".join([str(x) for x in [MAJOR_VER, MINOR_VER, PATCH_LEVEL]])+(f"-{EXTRA}" if EXTRA != None else "")

# Runtime folders
BASE_DIR = os.path.dirname(__file__)
SCR_DIR = os.path.join(BASE_DIR, "scripts")

class ExecutingInterrupt:
    '''
    Configurable script interrupt handler
    '''
    
    def __init__(self, exit_msg=None, exit=True) -> None:
        self.interrupt = False
    
    def _handler(self, signum, frame) -> None:
        self.interrupt = True
        self.signal = signum
        self.frame = frame
    
    def __enter__(self) -> None:
        self.old_sigint = signal.signal(signal.SIGINT, self._handler)
        self.old_sigterm = signal.signal(signal.SIGTERM, self._handler)
        return self
    
    def __exit__(self, type, value, traceback) -> None:
        signal.signal(signal.SIGINT, self.old_sigint)
        signal.signal(signal.SIGTERM, self.old_sigterm)

class LogFile:
    def __init__(self, file: str, parent=None) -> None:
        self.file = file
        self.have_parent = parent != None
        self.parent = parent
        if not check_dir(os.path.dirname(file)):
            create_dir(os.path.dirname(file))
        if not check_path(file):
            create_file(file)
            self.clear()
        if not check_file(file):
            printf(f"Given path '{file}' is not a file!", level='f')
        if type(parent) != type(self) and parent != None:
            printf(f"Parent log is not a LogFile object!", level='f')

    def read(self) -> str:
        return "".join(read(self.file)).rstrip()

    def write(self, data: str) -> None:
        write(self.file, data.replace("\n\n", "\n").replace("\n", f'\n[{time.strftime("%Y-%m-%d %H:%M:%S")} ({time.process_time()} from start)] '), append=True)

    def clear(self) -> None:
        write(self.file, "", append=False)
        self.write("# ---------- Start ----------\n" if not self.have_parent else "# ---------- Start ----------")

    def save_to_parent(self, prevscr: str = None) -> None:
        self.parent.write(f'Output of {"previous script" if prevscr == None else prevscr}:\n{self.read()}\n') if self.have_parent else do_nothing()

    def remove(self) -> None:
        remove(self.path)
        del(self)

# Thanks for inputimeout project
class TimeoutOccurred(Exception):
    pass

def echo(string):
    sys.stdout.write(string)
    sys.stdout.flush()

def posix_inputimeout(prompt='', timeout=30):
    echo(prompt)
    sel = selectors.DefaultSelector()
    sel.register(sys.stdin, selectors.EVENT_READ)
    events = sel.select(timeout)

    if events:
        key, _ = events[0]
        return key.fileobj.readline().rstrip("\n")
    else:
        echo("\n")
        termios.tcflush(sys.stdin, termios.TCIFLUSH)
        raise TimeoutOccurred()

# END

def debug_executor(executor):
    def wrap(*args, **kwargs):
        if DEBUG:
            try:
                _input = posix_inputimeout(prompt=f"Executor console is ACTIVE\nYou can debug executor with your own commands.\nPress ENTER on {INPUT_TIMEOUT} seconds or skip to continue...", timeout=INPUT_TIMEOUT)
            except TimeoutOccurred:
                _input = None
            if _input != None:
                printf("Now you will get a console. Type 'exit' when done.")
                pty.spawn("/bin/bash")
                while True:
                    _exec = input(f"Execute executor with args {args} {kwargs}? [y/n] ")
                    if _exec == None or _exec == "":
                        _exec = " "
                    break
                if _exec[0].lower() == 'n':
                    while True:
                        _ret = input("Return True of False [t/f] ")
                        if _ret == None or _ret == "":
                            _ret = " "
                        break
                    if _ret[0] == 't':
                        return True
                    else:
                        return False
        return executor(*args, **kwargs)
    return wrap

def do_nothing() -> None:
    pass

def printf(*message, level="i"):
    '''
    Formats message with level.
    Exit, when fatal. Like in customcmd.
    @param string (str): Output string
    @param level (str): Info level ([d]ebug|[v]erbose|[i]nfo|[e]rror|[w]arning|[f]atal) (Default: i)
    '''
    string = " ".join(message)
    _level = level[0].lower().strip()
    if _level == 'd' and not DEBUG:
        return
    if _level == 'v' and not VERBOSE:
        return
    msg = f"[{'*' if _level == 'i' else '!' if _level == 'w' else '@' if _level == 'e' else '~' if _level == 'd' else '.' if _level == 'v' else '&' if _level == 'f' else '?'}] {string}".replace("\n", "\n[`] ")
    print(msg)
    GLOBAL_LOG.write(msg)
    if _level == 'f':
        raise Exception(string)

def check_path(path: str) -> bool:
    return os.path.exists(path)

def check_dir(path: str) -> bool:
    if not check_path(path):
        return False
    if not os.path.isdir(os.path.realpath(path)):
        return False
    return True

def check_file(path) -> bool:
    if not check_path(path):
        return False
    if not os.path.isfile(os.path.realpath(path)):
        return False
    return True

def remove(path: str, recursive=False) -> None:
    if check_dir(path) and not recursive:
        printf(f"Ommiting {path} because not recursive deletion", level='w')
        return
    if not check_path(path):
        printf(f"Path not exists: {path}", level='e')
        return
    if not recursive and not check_dir(path):
        if os.path.islink(path):
            os.unlink(path)
        else:
            os.remove(path)
    else:
        shutil.rmtree(path)

def create_file(path: str) -> None:
    if check_dir(path):
        remove(path, recursive=True)
    if check_file(path):
        return
    try:
        file = open(path, "x", encoding="utf-8")
        file.close()
    except:
        return

def create_dir(path: str) -> None:
    if check_file(path):
        remove(path)
    if check_dir(path):
        return
    os.makedirs(path)

def write(path: str, data: str, append=False) -> None:
    try:
        create_file(path)
        file = open(path, "w" if not append else "a", encoding="utf-8")
        file.write(data)
        file.close()
    except:
        return

def read(path: str) -> list:
    try:
        file = open(path, "r", encoding="utf-8")
        data = file.readlines()
        file.close()
        return data
    except:
        return ""

@debug_executor
def execute(script: str, args="", exit_msg=None, exit=True):
    '''
    Runner of scripts under scripts folder.
    If script fails, it might to kill parent (this script) by $1 argument
    Basedir can be accessed by $2.
    Logging file is on $3 argument.
    '''
    script = os.path.join(SCR_DIR, f"{script}.sh")
    if not os.path.exists(script):
        raise Exception(f"No script found {script}")
    with ExecutingInterrupt() as ei:
        os.system(f"chmod 755 {script}")
        os.system(f"\"{script}\" {os.getpid()} \"{BASE_DIR}\" \"{SCRIPT_LOG.file}\" {'' if args == None else args if type(args) != list else ' '.join(args)}")
        interrupt = ei.interrupt
    SCRIPT_LOG.save_to_parent(prevscr=script)
    logs = SCRIPT_LOG.read()
    SCRIPT_LOG.clear()
    if interrupt:
        if not exit:
            return True
        printf(f"Error occured at {script}\n{logs}" if exit_msg == None else exit_msg, level='f')

def arg_parse():
    parser =  ArgumentParser(description="Build system for UnOS kernel", epilog="Under GNU v3 Public license. UnOS is not new OS, it is Linux rewrite to Rust")
    parser.add_argument("target", help="Build terget (clean will clear logs and data)", default="legacy", choices=["legacy", "clean", "efi", "bios"], metavar="TARGET", nargs="?")
    parser.add_argument("-v", "--verbose", help="Be verbose", action="store_true")
    parser.add_argument("-d", "--debug", help="Switch into debug configuration", action='store_true')
    parser.add_argument("--timeout", help="Timeout for input (for debug console)", type=int, default=5, metavar="TIMEOUT")
    parser.add_argument("--logdir", help="Logging directory", type=str, metavar="LOGDIR", default=os.path.join(BASE_DIR, "logs"))
    parser.add_argument("-a", "--arch", help="Build for ARCH", default="x86_64", choices=["x86_64"], metavar="ARCH")
    args = parser.parse_args()
    return args

def clean(logdir=None):
    execute("build/clean")
    remove(logdir, recursive=True) if logdir != None else do_nothing()
    sys.exit(0)

def build(arch: str, target: str) -> None:
    execute("build/prepare", args=f"\"{arch}\" \"{target}\"")
    execute("build_sys_install/rustup")
    execute("build_sys_install/toolchain", args=f"{arch}")
    execute("build_sys_install/components")
    execute("build/build", args=f"{'release' if not DEBUG else 'debug'}")
    execute("build/run", args=f"{'release' if not DEBUG else 'debug'}")

if __name__ != "__main__":
    exit()

args = arg_parse()
logdir = args.logdir

global DEBUG
global VERBOSE
global INPUT_TIMEOUT
global GLOBAL_LOG
global SCRIPT_LOG

DEBUG = args.debug
VERBOSE = args.verbose
INPUT_TIMEOUT = args.timeout
GLOBAL_LOG = LogFile(os.path.join(logdir, f'{time.strftime("%Y-%m-%d %H:%M:%S")}.log'))
SCRIPT_LOG = LogFile(os.path.join(logdir, 'script_logger.log'), parent=GLOBAL_LOG)

if args.target == "clean":
    clean(logdir=logdir)
else:
    if args.target != "legacy":
        printf(f"Feature {args.target} is unstable! There may be bugs with compiling!", level='w')
    build(args.arch, args.target)



def write_log(something: str) -> None:
    global GLOBAL_LOG
    write(GLOBAL_LOG, f'[{time.strftime("%Y-%m-%d %H:%M:%S")} ({time.process_time()} from start)] ' + something, append=True)

def remove_log(script_log=False) -> None:
    global GLOBAL_LOG
    global SCR_LOG
    remove(GLOBAL_LOG if not script_log else SCR_LOG)

def save_logs() -> None:
    data = read_log(script_log=True)
    write_log("Output of previous script: " + data) if data != "" and data != None and type(data) == str else do_nothing()

