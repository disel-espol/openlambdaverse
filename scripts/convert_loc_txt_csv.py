import csv
import re

def convert_txt_to_csv(input_file, output_file):
    # Initialize variables to store data
    data = []
    current_project_id = None
    current_language = None
    processing_sum = False  # Flag to indicate if SUM line is being processed

    # Read the input file
    with open(input_file, 'r') as f:
        lines = f.readlines()

    # Process the lines to capture project IDs and code analysis data
    for i, line in enumerate(lines):
        line = line.strip()

        # Check if the line is a project directory line
        if line.startswith("./"):
            current_project_id = line.split('/')[-2]
            processing_sum = False  # Reset the flag

        elif re.match(r'^Language\s+files\s+blank\s+comment\s+code', line):
            # Read the table rows
            j = i + 1
            while j < len(lines) and not lines[j].strip().startswith('SUM:'):
                parts = lines[j].strip().split()
                if len(parts) >= 5:
                    language, files, blank, comment, code = parts[:5]
                    data.append([current_project_id, language, files, blank, comment, code])
                j += 1

        elif line.startswith('SUM:'):
            # Process the SUM line
            if current_project_id:
                parts = re.findall(r'\d+', line)
                if len(parts) >= 4:
                    files, blank, comment, code = parts[:4]
                    data.append([current_project_id, 'SUM', files, blank, comment, code])
            processing_sum = True

        elif processing_sum and line.startswith('-' * 5):
            # Process the separator line under SUM
            continue

    # Write the data to the output CSV file
    with open(output_file, 'w', newline='') as csv_file:
        csv_writer = csv.writer(csv_file)
        # Write the CSV header
        csv_writer.writerow(['project_id', 'language', 'files', 'blank', 'comment', 'code'])
        # Write the data rows
        csv_writer.writerows(data)

    print(f'CSV file has been created: {output_file}')

# Example usage:
input_file = 'cloc/cloc_output.txt'
output_file = 'csvs/cloc_output.csv'
convert_txt_to_csv(input_file, output_file)
