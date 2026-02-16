# app/math_engine.py

import subprocess
import tempfile
import os
import shutil

def run_python_code(code: str, files: dict = None, timeout: int = 20):
    """
    Выполнить пользовательский Python-код в песочнице.
    files: dict с именем файла и содержимым для подгрузки во временную папку.
    Возвращает (stdout, stderr, path_to_graphics).
    """
    temp_dir = tempfile.mkdtemp()
    script_path = os.path.join(temp_dir, "user_code.py")
    graphics_dir = os.path.join(temp_dir, "graphics")
    os.makedirs(graphics_dir, exist_ok=True)

    # Поддержка пользовательских файлов
    if files:
        for fname, fcontent in files.items():
            fpath = os.path.join(temp_dir, fname)
            with open(fpath, "wb") as f:
                f.write(fcontent)

    # Код: переопределяем matplotlib backend и путь для графиков
    safe_code = (
        "import matplotlib; matplotlib.use('Agg')\n"
        "import matplotlib.pyplot as plt\n"
        f"import os\nos.makedirs('graphics', exist_ok=True)\n"
        + code +
        "\nfor i, fig in enumerate(plt.get_fignums()):\n"
        "    plt.figure(fig)\n"
        "    plt.savefig(f'graphics/figure_{i}.png')\n"
    )
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(safe_code)

    # Запуск кода
    try:
        result = subprocess.run(
            ["python", script_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=temp_dir
        )
        output = result.stdout
        error = result.stderr
        # Ищем png-картинки
        images = []
        if os.path.exists(graphics_dir):
            for fname in sorted(os.listdir(graphics_dir)):
                if fname.lower().endswith(".png"):
                    with open(os.path.join(graphics_dir, fname), "rb") as imgf:
                        images.append(imgf.read())
    except Exception as e:
        output, error, images = "", str(e), []
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
    return output, error, images
