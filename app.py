from flask import Flask, render_template, request, send_from_directory
from docx import Document
import os
import re

app = Flask(__name__)

# Utility Functions

def preprocess_mcq_lines(lines):
    """
    Processes input lines to identify questions and options,
    organizing them in a structured format.
    """
    processed_lines = []
    current_question = []
    in_options = False

    for line in lines:
        stripped_line = line.strip()
        if not stripped_line:  # Skip empty lines
            continue

        # Detect options with or without labels (e.g., (A), (B), A., B., etc.)
        option_match = re.match(r'^[\(\[]?[A-Za-z0-9][\)\]].*|^[A-Da-d]\..*', stripped_line)

        if option_match:
            if current_question and not in_options:  # Save previous question block
                processed_lines.append("\n".join(current_question).strip())
                current_question = []
            processed_lines.append(stripped_line)
            in_options = True
        else:
            # Part of the question
            current_question.append(stripped_line)
            in_options = False

    if current_question:  # Add the last question if any
        processed_lines.append("\n".join(current_question).strip())

    return processed_lines

def get_template_path(template_size):
    """
    Retrieves the file path for the template based on selected size.
    """
    template_files = {
        '25': "templates/template 25.docx",
        '50': "templates/template 50.docx",
        '100': "templates/template 100.docx",
        '125': "templates/template 125.docx",
        '150': "templates/template 150.docx",
        '200': "templates/template 200.docx"
    }
    return template_files.get(template_size)

# Core Functionality

def convert_text_to_word(lines, template_file):
    """
    Converts processed MCQ lines into a Word document format using a template file.
    """
    doc = Document(template_file)
    table_index = 0
    line_index = 0
    incorrect_options_lines = []

    lines = preprocess_mcq_lines(lines)
    question_number_pattern = re.compile(r'^(Q\.?\d+\.?|\d+\.?|\d+\))\s*')

    while table_index < len(doc.tables) and line_index < len(lines):
        # Collect question text
        question_lines = []
        while line_index < len(lines) and not re.match(r'^[\(\[]?[A-Za-z0-9][\)\]].*|^[A-Da-d]\..*', lines[line_index]):
            cleaned_line = re.sub(question_number_pattern, '', lines[line_index].strip())
            question_lines.append(cleaned_line)
            line_index += 1

        question = "\n".join(question_lines).strip()

        # Collect options and identify the correct answer
        options, correct_index = collect_options(lines, line_index)

        # Insert question and options into the current table
        populate_table(doc.tables[table_index], question, options, correct_index)
        
        # Move to the next table for the next question set
        table_index += 1

    return doc, incorrect_options_lines

def collect_options(lines, line_index):
    """
    Collects options and identifies the correct answer in the provided lines.
    """
    options = []
    correct_index = None
    while line_index < len(lines) and re.match(r'^[\(\[]?[A-Za-z0-9][\)\]].*|^[A-Da-d]\..*', lines[line_index]):
        option_line = lines[line_index].strip()
        option_text = option_line.split(')', 1)[-1].strip()  # Get text after label
        options.append(option_text)
        if '@' in option_line:  # Identify correct answer
            correct_index = len(options) - 1
        line_index += 1
    return options, correct_index

def populate_table(table, question, options, correct_index):
    """
    Populates the given table with question, options, and correct answer.
    """
    table.cell(0, 1).text = question
    table.cell(1, 1).text = 'multiple_choice'

    # Insert options
    table.cell(2, 1).text = options[0] if len(options) > 0 else ''
    table.cell(3, 0).text = options[1] if len(options) > 1 else ''
    table.cell(3, 2).text = options[2] if len(options) > 2 else ''
    table.cell(4, 1).text = options[3] if len(options) > 3 else ''

    # Insert correct answer index
    table.cell(4, 3).text = str(correct_index + 1) if correct_index is not None else ''

# Flask Routes

@app.route('/', methods=['GET', 'POST'])
def index():
    """
    Main route for displaying the form and processing MCQ input.
    """
    if request.method == 'POST':
        text_content, lines, file_text_map = process_input()
        if not lines and not file_text_map:
            return render_template('index.html', error="Please provide text content or upload a text file.")

        template_file_path = get_template_path(request.form['template_size'])
        if not template_file_path:
            return render_template('index.html', error="Invalid template size selected")

        output_data = handle_conversion(lines, file_text_map, template_file_path)
        return render_template('result.html', **output_data)

    return render_template('index.html')

def process_input():
    """
    Processes the input from text content and uploaded files.
    """
    text_content = request.form['text_content']
    lines = text_content.split('\n') if text_content else []
    text_files = request.files.getlist('text_files')
    file_text_map = {}

    for text_file in text_files:
        if text_file:
            file_content = text_file.read().decode('utf-8')
            file_text_map[text_file.filename] = file_content.split('\n')
    return text_content, lines, file_text_map

def handle_conversion(lines, file_text_map, template_file_path):
    """
    Handles the conversion process and generates output data for rendering results.
    """
    file_names = []
    output_file_path = None

    if lines:
        doc, incorrect_options_lines = convert_text_to_word(lines, template_file_path)
        output_file_path = f"static/output.docx"
        doc.save(output_file_path)

    for file_name, file_lines in file_text_map.items():
        doc, incorrect_options_lines = convert_text_to_word(file_lines, template_file_path)
        output_file_name = f"{os.path.splitext(file_name)[0]}_output.docx"
        output_file_path = f"static/{output_file_name}"
        doc.save(output_file_path)
        file_names.append(output_file_name)

    return {"output_file": "output.docx", "incorrect_options_lines": incorrect_options_lines, "file_names": file_names}

@app.route('/download/<filename>', methods=['GET'])
def download(filename):
    """
    Allows users to download the generated Word document.
    """
    return send_from_directory(os.path.join(os.getcwd(), 'static'), filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
