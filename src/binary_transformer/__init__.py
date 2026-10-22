
import base64
from io import BytesIO

import flet as ft
import flet_audio_recorder as far
import numpy as np
from PIL import Image

SAMPLE_RATE = 16000
CHANNELS = 1
MAX_SOUND_SAMPLES = 128


def is_numeric(value: str) -> bool:
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False


def is_hex(value: str) -> bool:
    try:
        int(value, 16)
        return True
    except (ValueError, TypeError):
        return False


def main(page: ft.Page):
    page.title = "Binary converter"
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.scroll = ft.ScrollMode.AUTO

    def reset_fields():
        bin_field.value = ""
        hex_field.value = ""
        dec_field.value = ""
        text_field.value = ""

    def handle_switch_change(e):
        selected_value = next(iter(e.control.selected))
        reset_fields()

        match selected_value:
            case "dec_to_bin":
                main_block.content = dec_to_bin_col
            case "hex_to_bin":
                main_block.content = hex_to_bin_col
            case "text_to_bin":
                main_block.content = text_to_bin_col
            case "img_to_bin":
                handle_img_input(None)
                main_block.content = img_to_bin_col
            case "sound_to_bin":
                main_block.content = sound_to_bin_col

        page.update()

    def handle_dec_input(e):
        text = (e.control.value or "").strip().replace(",", ".")
        if not text:
            bin_field.value = ""
        elif is_numeric(text):
            try:
                if "." in text:
                    integer_part, fractional_part = text.split(".", 1)
                    if integer_part in ("", "-"):
                        integer_part += "0"
                    if fractional_part.isdigit():
                        integer_bits = (
                            ("-" if integer_part.startswith("-") else "")
                            + bin(abs(int(integer_part)))[2:]
                        )
                        fractional_bits = (
                            bin(int(fractional_part))[2:]
                            if fractional_part
                            else ""
                        )
                        bin_field.value = (
                            f"{integer_bits},{fractional_bits}"
                            if fractional_bits
                            else integer_bits
                        )
                    else:
                        bin_field.value = "Введи коректне число."
                else:
                    number = int(text)
                    bin_field.value = (
                        ("-" if number < 0 else "") + bin(abs(number))[2:]
                    )
            except ValueError:
                bin_field.value = "Введи коректне число."
        else:
            bin_field.value = "Введи коректне число."
        page.update()

    def handle_hex_input(e):
        text = (e.control.value or "").strip().replace("#", "")
        if not text:
            bin_field.value = ""
        elif is_hex(text):
            bin_field.value = bin(int(text, 16))[2:].zfill(len(text) * 4)
        else:
            bin_field.value = "Введи коректне шістнадцяткове число."
        page.update()

    def handle_text_input(e):
        text = e.control.value or ""
        bin_field.value = " ".join(f"{byte:08b}" for byte in text.encode("utf-8"))
        page.update()

    def handle_img_input(e):
        noise = np.random.randint(0, 2, size=(10, 10), dtype=np.uint8)
        flat_string = "".join(map(str, noise.flatten()))
        bin_field.value = flat_string

        img = Image.new("1", (10, 10))
        img.putdata([int(bit) for bit in flat_string])
        img_large = img.resize((200, 200), resample=Image.Resampling.NEAREST)

        buffered = BytesIO()
        img_large.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        image.src = f"data:image/png;base64,{img_base64}"
        page.update()

    sound_buffer = bytearray()

    def handle_audio_stream(e: far.AudioRecorderStreamEvent):        sound_buffer.extend(e.chunk)

    recorder = far.AudioRecorder(on_stream=handle_audio_stream)

    def pcm_to_binary(data: bytes, max_samples: int = MAX_SOUND_SAMPLES) -> str:
        sample_count = min(len(data) // 2, max_samples)
        bit_groups = []

        for index in range(sample_count):
            start = index * 2
            sample = int.from_bytes(
                data[start:start + 2],
                byteorder="little",
                signed=True,
            )
            bit_groups.append(f"{sample & 0xFFFF:016b}")

        return " ".join(bit_groups)

    async def start_sound_recording(e):
        try:
            if not await recorder.has_permission():
                sound_status.value = (
                    "Немає дозволу на використання мікрофона. "
                    "Дозволь доступ у налаштуваннях пристрою/браузера."
                )
                page.update()
                return

            sound_buffer.clear()
            bin_field.value = ""
            sound_status.value = "Запис триває..."
            start_sound_button.disabled = True
            stop_sound_button.disabled = False
            page.update()

            started = await recorder.start_recording(
                configuration=far.AudioRecorderConfiguration(
                    encoder=far.AudioEncoder.PCM16BITS,
                    sample_rate=SAMPLE_RATE,
                    channels=CHANNELS,
                )
            )

            if started is False:
                sound_status.value = "Не вдалося розпочати запис."
                start_sound_button.disabled = False
                stop_sound_button.disabled = True
                page.update()

        except Exception as ex:
            start_sound_button.disabled = False
            stop_sound_button.disabled = True
            sound_status.value = f"Помилка запису: {ex}"
            page.update()

    async def stop_sound_recording(e):
        try:
            await recorder.stop_recording()

            if not sound_buffer:
                sound_status.value = (
                    "Аудіодані не отримано. Перевір мікрофон і дозвіл на запис."
                )
                bin_field.value = ""
                return

            if len(sound_buffer) % 2:
                sound_buffer.pop()

            sample_count = len(sound_buffer) // 2
            shown_samples = min(sample_count, MAX_SOUND_SAMPLES)
            bin_field.value = pcm_to_binary(bytes(sound_buffer))
            duration = sample_count / SAMPLE_RATE

            sound_status.value = (
                f"Запис завершено: {duration:.2f} с, "
                f"{sample_count:,} відліків. "
                f"Показано перші {shown_samples} відліків "
                f"({shown_samples * 16} біт)."
            )

        except Exception as ex:
            sound_status.value = f"Помилка зупинки запису: {ex}"

        finally:
            start_sound_button.disabled = False
            stop_sound_button.disabled = True
            page.update()

    mode_switcher = ft.SegmentedButton(
        selected=["dec_to_bin"],
        allow_multiple_selection=False,
        allow_empty_selection=False,
        on_change=handle_switch_change,
        segments=[
            ft.Segment(
                value="dec_to_bin",
                label=ft.Text("Десятковий → двійковий"),
                icon=ft.Icon(ft.Icons.ONETWOTHREE_SHARP),
            ),
            ft.Segment(
                value="hex_to_bin",
                label=ft.Text("Шістнадцятковий → двійковий"),
                icon=ft.Icon(ft.Icons.NUMBERS_SHARP),
            ),
            ft.Segment(
                value="text_to_bin",
                label=ft.Text("Текст → двійковий"),
                icon=ft.Icon(ft.Icons.TEXT_SNIPPET_SHARP),
            ),
            ft.Segment(
                value="img_to_bin",
                label=ft.Text("Зображення → двійковий"),
                icon=ft.Icon(ft.Icons.IMAGE_SHARP),
            ),
            ft.Segment(
                value="sound_to_bin",
                label=ft.Text("Звук → двійковий"),
                icon=ft.Icon(ft.Icons.MULTITRACK_AUDIO_SHARP),
            ),
        ],
    )

    dec_field = ft.TextField(
        label="Десяткове число",
        on_change=handle_dec_input,
        multiline=True,
        min_lines=1,
        max_lines=4,
        width=600,
    )
    hex_field = ft.TextField(
        label="Шістнадцяткове число",
        on_change=handle_hex_input,
        multiline=True,
        min_lines=1,
        max_lines=4,
        width=600,
    )
    text_field = ft.TextField(
        label="Текст",
        on_change=handle_text_input,
        multiline=True,
        min_lines=1,
        max_lines=6,
        width=600,
    )
    bin_field = ft.TextField(
        label="Двійковий код",
        read_only=True,
        multiline=True,
        min_lines=3,
        max_lines=10,
        width=600,
    )

    img_regen_button = ft.Button(
        "Рандомізувати картинку",
        icon=ft.Icons.REPLAY_SHARP,
        on_click=handle_img_input,
    )
    image = ft.Image(
        src="",
        fit=ft.BoxFit.CONTAIN,
        width=200,
        height=200,
    )

    sound_status = ft.Text("Натисни \"Почати запис\", скажи щось і зупини запис.")
    start_sound_button = ft.Button(
        "Почати запис",
        icon=ft.Icons.MIC,
        on_click=start_sound_recording,
    )
    stop_sound_button = ft.Button(
        "Зупинити запис",
        icon=ft.Icons.STOP,
        on_click=stop_sound_recording,
        disabled=True,
    )

    dec_to_bin_col = ft.Column(
        [dec_field, bin_field],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        tight=True,
    )
    hex_to_bin_col = ft.Column(
        [hex_field, bin_field],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        tight=True,
    )
    text_to_bin_col = ft.Column(
        [text_field, bin_field],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        tight=True,
    )
    img_to_bin_col = ft.Column(
        [image, img_regen_button, bin_field],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        tight=True,
    )
    sound_to_bin_col = ft.Column(
        [
            ft.Row(
                [start_sound_button, stop_sound_button],
                alignment=ft.MainAxisAlignment.CENTER,
                wrap=True,
            ),
            sound_status,
            bin_field,
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        tight=True,
    )

    main_block = ft.Container(
        content=dec_to_bin_col,
        width=650,
        padding=10,
    )

    page.add(
        ft.Column(
            [
                mode_switcher,
                ft.Container(height=20),
                main_block,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )
    )


if __name__ == "__main__":
    ft.run(main)
