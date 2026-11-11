"""Read the files explicitly delivered with one request."""
import re
import stat
from xml.etree import ElementTree
import zipfile


TEXT_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".rst", ".json", ".jsonl", ".csv", ".tsv", ".log",
    ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".xml", ".html", ".htm",
    ".py", ".js", ".jsx", ".ts", ".tsx", ".css", ".sql", ".ps1", ".bat", ".cmd",
    ".sh", ".c", ".cpp", ".h", ".hpp", ".cs", ".java", ".go", ".rs", ".diff", ".patch",
}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
MAX_FILE_BYTES = 12 * 1024 * 1024
MAX_REQUEST_CHARS = 24_000
MAX_TEXT_CHARS = 70_000
MAX_ATTACHMENTS = 16
MAX_IMAGES = 4


def ordinary(path, directory=False):
    try:
        info = path.lstat()
    except OSError:
        return False
    if getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
        return False
    check = stat.S_ISDIR if directory else stat.S_ISREG
    return check(info.st_mode)


def bounded_bytes(path):
    if not ordinary(path):
        raise ValueError("文件不可读，或是链接/重解析点")
    with path.open("rb") as stream:
        data = stream.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("单个附件超过 12 MiB")
    return data


def decode_text(data):
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = data.decode("utf-16")
    else:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = data.decode("gb18030")
    if re.search(r"[\x00-\x08\x0e-\x1f]", text):
        raise ValueError("文件看起来不是文本")
    return text


def read_docx(data):
    from io import BytesIO

    with zipfile.ZipFile(BytesIO(data)) as doc:
        info = doc.getinfo("word/document.xml")
        if info.file_size > MAX_FILE_BYTES:
            raise ValueError("DOCX 正文超过 12 MiB")
        root = ElementTree.fromstring(doc.read(info))
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    return "\n".join(
        "".join(text.text or "" for text in paragraph.iter(ns + "t"))
        for paragraph in root.iter(ns + "p")
    )


def read_pdf(data):
    from io import BytesIO

    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ValueError("PDF 文本提取需要安装 pypdf，见使用说明") from exc
    reader = PdfReader(BytesIO(data))
    if reader.is_encrypted:
        raise ValueError("PDF 已加密")
    pages = reader.pages
    text = "\n\n".join(pages[index].extract_text() or "" for index in range(min(30, len(pages))))
    if not text.strip():
        raise ValueError("没有可提取的文字。扫描件可以发送相关页面的图片")
    return text, len(pages) > 30


def file_text(path):
    extension = path.suffix.lower()
    if extension in TEXT_EXTENSIONS or not extension:
        return decode_text(bounded_bytes(path)), False
    if extension == ".docx":
        return read_docx(bounded_bytes(path)), False
    if extension == ".pdf":
        return read_pdf(bounded_bytes(path))
    raise ValueError(f"暂不支持 {extension} 格式")


def split_source(source):
    if ordinary(source, directory=True):
        candidates = [source / name for name in ("request.md", "request.txt")]
        primary = [path for path in candidates if ordinary(path)]
        if len(primary) != 1:
            raise ValueError("请求文件夹必须包含且只包含一个 request.md 或 request.txt")
        attachments = [
            path for path in source.iterdir()
            if path.name not in {"READY", "request.md", "request.txt", "attachments"}
            and not path.name.startswith(".")
        ]
        folder = source / "attachments"
        if folder.exists() or folder.is_symlink():
            if not ordinary(folder, directory=True):
                raise ValueError("attachments 必须是本机的普通文件夹")
            attachments.extend(path for path in folder.iterdir() if not path.name.startswith("."))
        return primary[0], sorted(attachments, key=lambda path: path.name.casefold())
    if ordinary(source):
        return (source, []) if source.suffix.lower() in {".txt", ".md", ".markdown"} else (None, [source])
    raise ValueError("找不到可读取的请求文件")


def collect(source, temporary):
    primary, attachments = split_source(source)
    if primary:
        request, _ = file_text(primary)
        if not request.strip():
            raise ValueError("请求文件是空的")
        if len(request) > MAX_REQUEST_CHARS:
            raise ValueError("请求正文超过 24000 字符，请将参考资料另存为附件")
    else:
        request = "请阅读收到的文件，回答其中提出的问题；如果没有具体问题，请概括要点并指出缺少的任务信息。"
    sections, images, notes = [], [], []
    remaining = MAX_TEXT_CHARS - len(request)
    if len(attachments) > MAX_ATTACHMENTS:
        notes.append(f"附件超过 {MAX_ATTACHMENTS} 个，只读取按文件名排序的前 {MAX_ATTACHMENTS} 个。")
    for path in attachments[:MAX_ATTACHMENTS]:
        try:
            extension = path.suffix.lower()
            if extension in IMAGE_EXTENSIONS:
                if len(images) >= MAX_IMAGES:
                    raise ValueError(f"一次最多附带 {MAX_IMAGES} 张图片")
                target = temporary / f"image-{len(images) + 1}{extension}"
                target.write_bytes(bounded_bytes(path))
                images.append(target)
                sections.append(f"图片 {len(images)}：{path.name}")
                continue
            if remaining <= 0:
                raise ValueError("文本附件容量已用完")
            content, page_limit = file_text(path)
            if not content.strip():
                raise ValueError("文件里没有可读文字")
            clipped = content[:remaining]
            sections.append(f"附件 {path.name}\n{clipped}")
            remaining -= len(clipped)
            if len(clipped) < len(content) or page_limit:
                notes.append(f"{path.name}：已按容量或页数上限截取。")
        except Exception as exc:
            notes.append(f"{path.name}：{exc}")
    if primary is None and not sections:
        raise ValueError("没有可读取的文件。" + " ".join(notes))
    return request, sections, images, notes
