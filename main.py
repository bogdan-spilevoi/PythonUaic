from pathlib import Path
from path_utilities import is_valid_path, is_valid_file
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--file", action="store_true")
args = parser.parse_args()

paths = []




def main():

    get_paths()

    print(paths)






def get_paths():
    if args.file:
        line = input("Enter path for file: ")
        try_paths_dir = is_valid_file(line)
        if not try_paths_dir.ok:
            print(try_paths_dir.error)
            return

        with open(try_paths_dir.value, "r") as f:
            for ln in f:
                try_local_dir = is_valid_path(ln.strip())

                if not try_local_dir.ok:
                    print(try_local_dir.error)
                    continue

                paths.append(try_local_dir.value)
    else:
        while True:
            line = input("Enter path (or [end]):")
            if line == "end":
                break
            
            try_local_dir = is_valid_path(line)

            if not try_local_dir.ok:
                print(try_local_dir.error)
                continue

            paths.append(try_local_dir.value)


if __name__ == "__main__":
    main()







































