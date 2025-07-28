import os
import yaml
import csv
from dotenv import load_dotenv

# --- Load .env file for external SSD or custom clone location ---
load_dotenv()
DEFAULT_CONFIG_FILES_DIR_FALLBACK = "config_files"
CONFIG_FILES_DIR = os.getenv("CONFIG_FILES_DIRECTORY", DEFAULT_CONFIG_FILES_DIR_FALLBACK)
# Parent directory containing GitHub repositories
directory = CONFIG_FILES_DIR

# Initialize an empty list to store the extracted data
data_list = []

# Function to replace tab characters with spaces in a string
def replace_tabs_with_spaces(text, spaces=2):
    return text.replace('\t', ' ' * spaces)

# Define custom constructors for CloudFormation intrinsic functions
def ref_constructor(loader, node):
    return loader.construct_scalar(node)

def get_att_constructor(loader, node):
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    else:
        return loader.construct_mapping(node)

def select_constructor(loader, node):
    return loader.construct_sequence(node)

def sub_constructor(loader, node):
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    else:
        return loader.construct_mapping(node)

def join_constructor(loader, node):
    return loader.construct_sequence(node)

# Custom constructor for !ImportValue
def import_value_constructor(loader, node):
    return loader.construct_scalar(node)

# Custom constructor for !Split
def split_constructor(loader, node):
    return loader.construct_sequence(node)

# Custom constructor for !GetAZs
def get_azs_constructor(loader, node):
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    else:
        return loader.construct_mapping(node)

def get_and_constructor(loader, node):
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    else:
        return loader.construct_mapping(node)

def get_or_constructor(loader, node):
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    else:
        return loader.construct_mapping(node)

def get_not_constructor(loader, node):
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    else:
        return loader.construct_mapping(node)

def get_equals_constructor(loader, node):
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    else:
        return loader.construct_mapping(node)

def get_if_constructor(loader, node):
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    else:
        return loader.construct_mapping(node)

def get_condition_constructor(loader, node):
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    else:
        return loader.construct_mapping(node)

yaml.SafeLoader.add_constructor('!Ref', ref_constructor)
yaml.SafeLoader.add_constructor('!GetAtt', get_att_constructor)
yaml.SafeLoader.add_constructor('!Select', select_constructor)
yaml.SafeLoader.add_constructor('!Sub', sub_constructor)
yaml.SafeLoader.add_constructor('!Join', join_constructor)
yaml.SafeLoader.add_constructor('!ImportValue', import_value_constructor)
yaml.SafeLoader.add_constructor('!Split', split_constructor)
yaml.SafeLoader.add_constructor('!GetAZs', get_azs_constructor)
yaml.SafeLoader.add_constructor('!And', get_and_constructor)
yaml.SafeLoader.add_constructor('!Or', get_or_constructor)
yaml.SafeLoader.add_constructor('!Not', get_not_constructor)
yaml.SafeLoader.add_constructor('!Equals', get_equals_constructor)
yaml.SafeLoader.add_constructor('!If', get_if_constructor)
yaml.SafeLoader.add_constructor('!Condition', get_condition_constructor)

# Iterate through the files in the directory
for filename in os.listdir(directory):
    if filename.endswith('.yml') or filename.endswith('.yaml'):
        file_path = os.path.join(directory, filename)
        print(file_path)
        
        # Load the YAML file, replace tabs with spaces, and then parse it
        with open(file_path, 'r') as yaml_file:
            yaml_text = yaml_file.read()
            yaml_text = replace_tabs_with_spaces(yaml_text)
            data = yaml.load(yaml_text, Loader=yaml.SafeLoader)

            # Extract the information and format it
            project_id, _ = os.path.splitext(filename)

            # Extract the information if the provider name is 'aws'
            if 'provider' in data:
                provider = data.get('provider')
                if isinstance(provider, str):
                    if not provider == 'aws':
                        continue
                else:
                    # Handle the case where 'provider' is an object
                    provider_name = provider.get('name', 'N/A')
                    if not provider_name == 'aws':
                        continue
            
            if 'functions' in data:
                functions = data['functions']
                if isinstance(functions, dict):
                    # 'functions' is a dictionary
                    for function_name, function_data in functions.items():
                        if function_data is None:
                            # Handle the case where function_data is None
                            data_list.append([project_id, function_name, 'N/A'])
                            continue

                        if isinstance(function_data, str):
                            # Handle the case where function_data is a string
                            data_list.append([project_id, function_name, 'N/A'])
                            continue

                        if 'events' not in function_data:
                            # Handle the case where 'events' key is missing, indicating an empty function
                            data_list.append([project_id, function_name, 'N/A'])
                            continue

                        events_info = function_data.get('events', [])
                        if isinstance(events_info, list):
                            # Handle the case where 'events_info' is a list of dictionaries
                            for event_dict in events_info:
                                if isinstance(event_dict, dict):
                                    for event_type in event_dict.keys():
                                        data_list.append([project_id, function_name, event_type])
                                else:
                                    # Handle the case where 'event_dict' is not a dictionary
                                    # Supposing a string
                                    event_type = event_dict
                                    data_list.append([project_id, function_name, event_type])
                        elif isinstance(events_info, dict):
                            # Handle the case where 'events_info' is a dictionary
                            for event_type in events_info.keys():
                                data_list.append([project_id, function_name, event_type])
                        else:
                            # Handle other cases where 'events_info' is not as expected
                            data_list.append([project_id, function_name, 'N/A'])

# Write the information to a CSV file
output_csv_file = 'csvs/events.csv'
os.makedirs(os.path.dirname(output_csv_file), exist_ok=True)
with open(output_csv_file, 'w', newline='') as csv_file:
    csv_writer = csv.writer(csv_file)
    csv_writer.writerow(['project_id', 'function_name', 'event'])
    csv_writer.writerows(data_list)

print(f'CSV file "{output_csv_file}" has been created with the extracted data.')
