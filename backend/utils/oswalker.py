import os

BLOCKED_DIRS = {'.git', '__pycache__', 'node_modules', '.venv'}
def is_valid_dir(path):
    path_parts = path.split(os.sep)
    return not any(part in BLOCKED_DIRS for part in path_parts)


CODE_EXTENSIONS = [".c", ".cpp", ".h", ".hpp", ".java", ".py",".rb", ".rs", ".go", ".js", ".ts", ".cs", ".swift", ".kt", ".m", ".php"]
def valid_extension(path):
    if any(path.endswith(ext) for ext in CODE_EXTENSIONS) :
        return path

def filter_path(path):
    dir_path = os.path.dirname(path)
    return(
        is_valid_dir(dir_path) and
        valid_extension(path)
    )

def find_files(root_path) :
    file_paths = []
    for (dirpath, dirnames, filenames) in os.walk(root_path) :
        for file in filenames:
            file_path = os.path.join(dirpath, file)
            if filter_path(file_path):
                file_paths.append(file_path)
    return file_paths

  



