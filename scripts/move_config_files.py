import os
import shutil
import fnmatch
from dotenv import load_dotenv

# --- Load .env file for external SSD or custom clone location ---
load_dotenv()
DEFAULT_CLONE_DIR_FALLBACK = "cloned_aws_repos"
DEFAULT_CONFIG_FILES_DIR_FALLBACK = "config_files"
CLONE_DIR = os.getenv("CLONED_REPOS_DIRECTORY", DEFAULT_CLONE_DIR_FALLBACK)
CONFIG_FILES_DIR = os.getenv("CONFIG_FILES_DIRECTORY", DEFAULT_CONFIG_FILES_DIR_FALLBACK)

# Parent directory containing GitHub repositories
parent_directory = CLONE_DIR
target_directory = CONFIG_FILES_DIR
# Create the target directory if it doesn't exist
os.makedirs(target_directory, exist_ok=True)

# Counter to keep track of copied files
total_copied_files = 0

# Iterate through subdirectories (GitHub repositories) in the parent directory
for repo_name in os.listdir(parent_directory):
    repo_directory = os.path.join(parent_directory, repo_name)
    
    # Check if the subdirectory is a directory (GitHub repository)
    if os.path.isdir(repo_directory):
        # Create a counter for naming subsequent files
        counter = 0
        
        # Recursively search for YML files within the GitHub repository directory
        for root, _, files in os.walk(repo_directory):
            for filename in files:
                if fnmatch.fnmatch(filename, '*serverless.yml'):
                    file_path = os.path.join(root, filename)
                    
                    # Check the content of the YML file to determine its purpose
                    with open(file_path, 'r') as yml_file:
                        yml_content = yml_file.read()
                    
                    if 'provider:' in yml_content or 'functions:' in yml_content:             
                        file_without_extension = os.path.splitext(filename)[0]
                        counter += 1
                        if counter == 1:
                            new_filename = f"{repo_name}_{file_without_extension}.yml"
                        else:
                            new_filename = f"{repo_name}_{file_without_extension}_{counter}.yml"
                        
                        destination_path = os.path.join(target_directory, new_filename)
                        
                        # Copy the file with the specified name to the target directory
                        shutil.copy(file_path, destination_path)
                        total_copied_files += 1
                        print(f"Copied: {file_path} -> {destination_path}")

# Print the total number of copied files
print(f"Total copied files: {total_copied_files}")
