from flask import Flask, render_template, request, redirect, flash, url_for
import fitz  # PyMuPDF for PDF handling
import requests  # To interact with GitHub API
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # For flash messages

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

main_text = []
main_gui = []
source_texts = []
source_gui = []
plag_ratio = 0.0
file_dict = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(file):
    """Extract text from a PDF file using PyMuPDF."""
    text = ""
    pdf_document = fitz.open(stream=file.read(), filetype="pdf")
    for page_num in range(pdf_document.page_count):
        page = pdf_document[page_num]
        text += page.get_text()
    pdf_document.close()
    return text

def read_file(file_content):
    """Process the main text file or PDF."""
    main_text.clear()
    main_gui.clear()
    text_lines = file_content.splitlines()
    word_id = 0
    for line in text_lines:
        for word in line.split():
            main_text.append(word.translate(str.maketrans('', '', r"""!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~‘’“”""")).lower())
            main_gui.append([word, False, False])
            word_id += 1
        main_gui[word_id - 1][2] = True

def read_files(file_contents):
    """Process the source files or PDFs."""
    source_gui.clear()
    source_texts.clear()
    file_id = 0
    for file_content in file_contents:
        source_texts.append([])
        source_gui.append([])
        text_lines = file_content.splitlines()
        word_id = 0
        for line in text_lines:
            for word in line.split():
                source_gui[file_id].append([word, 0, False])
                source_texts[file_id].append(word.translate(str.maketrans('', '', r"""!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~“”""")).lower())
                word_id += 1
            source_gui[file_id][word_id - 1][2] = True
        file_id += 1

def get_github_file_content(url):
    """Fetch file content from a raw GitHub file URL."""
    response = requests.get(url)
    if response.status_code == 200:
        return response.text
    else:
        return ""

def deleteGUI():
    for word in main_gui:
        word[1] = False
    for file in source_gui:
        for word in file:
            word[1] = 0

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        N = int(request.form.get('N'))
        global mainfilename
        mainfile = request.files.get('mainfile')
        otherfiles = request.files.getlist('otherfiles')
        github_url = request.form.get('github_url')

        if not mainfile and not otherfiles and not github_url:
            flash('No files selected.', 'error')
            return redirect(url_for('index'))

        # Process the main file (PDF or text)
        if mainfile and allowed_file(mainfile.filename):
            if mainfile.filename.endswith('.pdf'):
                file_content = extract_text_from_pdf(mainfile)
            else:
                file_content = mainfile.read().decode('utf-8')

            file_dict[-1] = mainfile.filename
            mainfilename = mainfile.filename
            read_file(file_content)
            flash(f'Main file "{mainfile.filename}" uploaded successfully.', 'success')
        else:
            flash('Invalid main file type.', 'error')
            return redirect(url_for('index'))

        # Process other uploaded files (PDF or text)
        file_contents = []
        for i, file in enumerate(otherfiles):
            if allowed_file(file.filename):
                if file.filename.endswith('.pdf'):
                    file_content = extract_text_from_pdf(file)
                else:
                    file_content = file.read().decode('utf-8')
                file_contents.append(file_content)
                file_dict[i] = file.filename
                flash(f'File "{file.filename}" uploaded successfully.', 'success')

        # Fetch files from GitHub if a URL is provided
        if github_url:
            github_file_content = get_github_file_content(github_url)
            if github_file_content:
                file_contents.append(github_file_content)
                file_dict[len(file_dict)] = "GitHub_File"
                flash('GitHub file content fetched successfully.', 'success')

        read_files(file_contents)

        result = check(N)
        return render_template('result.html', result=result, files=file_dict, mainfile=mainfilename, plag_ratio=plag_ratio // 1, N=N)

    return redirect(url_for('index'))

@app.route('/recheck', methods=['GET', 'POST'])
def recheck():
    if request.method == 'POST':
        deleteGUI()
        N = int(request.form.get('N'))
        result = check(N)
        return render_template('result.html', result=result, files=file_dict, mainfile=mainfilename, plag_ratio=plag_ratio // 1, N=N)

def check(N):
    n = N - 1
    main_N = main_text[:N - 1].copy()
    main_len = len(main_text)
    for id in range(main_len - n):
        main_N.append(main_text[id + n])
        for file_id in range(len(source_texts)):
            for j in range(len(source_texts[file_id]) - n):
                if main_N == source_texts[file_id][j:j + N]:
                    for k in range(N):
                        main_gui[id + k][1] = True
                        main_gui[id + k][2] = [file_id, j + k]
                        source_gui[file_id][j + k][1] = True
        main_N.pop(0)
    return [html_format(i) for i in range(-1, len(source_gui))]

def html_format(fileid):
    if fileid == -1:
        main_html = ["<p> "]
        plag_count, word_count = 0, 0
        global plag_ratio
        for word in range(len(main_text)):
            if main_gui[word][1]:
                main_html.append(f'<a href="#w{main_gui[word][2][0] + 1}-{main_gui[word][2][1]}" style="color:red;">{main_gui[word][0]}</a> ')
                plag_count += 1
            else:
                main_html.append(main_gui[word][0] + " ")
            word_count += 1
            if main_gui[word][2] == True:
                main_html.append("</p><p>")
        plag_ratio = (plag_count / word_count) * 100
        return "".join(main_html)
    else:
        comp_text = [f"<h2>#{fileid + 1} - {file_dict[fileid]}</h2><p> "]
        for word in source_gui[fileid]:
            if word[1]:
                comp_text.append(f'<span id="w{fileid + 1}-{source_gui[fileid].index(word)}" style="color:red;">{word[0]}</span> ')
            else:
                comp_text.append(word[0] + " ")
        return "".join(comp_text)

if __name__ == '__main__':
    app.run(debug=True)
