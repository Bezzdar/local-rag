import os
import fitz  # PyMuPDF
import re

def extract_text_pymupdf(pdf_path):
    doc = fitz.open(pdf_path)
    full_text = ""
    for page in doc:
        full_text += page.get_text()
    return full_text

def split_text_to_chunks(text, chunk_size=800, overlap=100):
    # Простая нарезка по символам с overlap (можно заменить на SentenceSplitter)
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if len(chunk.strip()) > 40:
            chunks.append(chunk.strip())
        start += chunk_size - overlap
    return chunks

def is_garbage(text, min_letters_ratio=0.15):
    text = text.strip()
    if len(text) < 40:
        return True
    total = len(text)
    rus_lat = len(re.findall(r'[A-Za-zА-Яа-яЁё]', text))
    ratio = rus_lat / total if total > 0 else 0
    return ratio < min_letters_ratio

def process_folder(folder_path, chunk_size=800, overlap=100, min_letters_ratio=0.15):
    pdf_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.pdf')]
    if not pdf_files:
        print("Нет PDF-файлов в папке!")
        return
    for filename in pdf_files:
        path = os.path.join(folder_path, filename)
        text = extract_text_pymupdf(path)
        print(f"\n=== {filename} ===")
        print(f"Общий объём текста: {len(text)} символов")
        chunks = split_text_to_chunks(text, chunk_size=chunk_size, overlap=overlap)
        good, bad = 0, 0
        for i, chunk in enumerate(chunks):
            if is_garbage(chunk, min_letters_ratio):
                bad += 1
            else:
                good += 1
        print(f"Всего чанков: {len(chunks)} | Живых: {good} | Битых: {bad}")
        # Примеры чанков:
        print("--- Пример хороших чанков ---")
        show = 0
        for i, chunk in enumerate(chunks):
            if not is_garbage(chunk, min_letters_ratio):
                print(f"\n[GOOD #{show+1}] {chunk[:400]}{'...' if len(chunk) > 400 else ''}")
                show += 1
                if show == 2: break
        show = 0
        print("--- Пример битых чанков ---")
        for i, chunk in enumerate(chunks):
            if is_garbage(chunk, min_letters_ratio):
                print(f"\n[BAD #{show+1}] {chunk[:400]}{'...' if len(chunk) > 400 else ''}")
                show += 1
                if show == 2: break

if __name__ == "__main__":
    folder = "."
    process_folder(folder, chunk_size=800, overlap=100, min_letters_ratio=0.15)
