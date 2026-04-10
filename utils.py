ALLOWED_EXTENSIONS = {'doc', 'docx', 'xls', 'xlsx', 'pdf', 'ppt', 'pptx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
