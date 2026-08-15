"""Protect dollar-delimited TeX from Markdown inline parsing."""

import hashlib
import html

from markdown.extensions import Extension
from markdown.postprocessors import Postprocessor
from markdown.preprocessors import Preprocessor


def _is_escaped(text: str, position: int) -> bool:
    backslashes = 0
    position -= 1
    while position >= 0 and text[position] == "\\":
        backslashes += 1
        position -= 1
    return backslashes % 2 == 1


def _find_display_end(text: str, start: int) -> int | None:
    position = start
    while (position := text.find("$$", position)) != -1:
        if not _is_escaped(text, position):
            return position
        position += 2
    return None


def _find_inline_end(text: str, start: int) -> int | None:
    position = start
    line_end = text.find("\n", start)
    if line_end == -1:
        line_end = len(text)
    while position < line_end:
        position = text.find("$", position, line_end)
        if position == -1:
            return None
        adjacent_to_dollar = (position > 0 and text[position - 1] == "$") or (
            position + 1 < len(text) and text[position + 1] == "$"
        )
        if not _is_escaped(text, position) and not adjacent_to_dollar:
            return position
        position += 1
    return None


def _placeholder(source: str) -> str:
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    return f"FOLIATEMATHPLACEHOLDER{digest}X"


def protect_dollar_math(content: str) -> tuple[str, dict[str, str]]:
    """Replace complete dollar-math spans while leaving code spans untouched."""
    output: list[str] = []
    protected: dict[str, str] = {}
    position = 0

    while position < len(content):
        if content[position] == "`":
            run_length = 1
            while (
                position + run_length < len(content)
                and content[position + run_length] == "`"
            ):
                run_length += 1
            delimiter = "`" * run_length
            end = content.find(delimiter, position + run_length)
            if end != -1:
                end += run_length
                output.append(content[position:end])
                position = end
                continue

        if content.startswith("$$", position) and not _is_escaped(content, position):
            math_end = _find_display_end(content, position + 2)
            if math_end is not None:
                math_end += 2
                source = content[position:math_end]
                marker = _placeholder(source)
                protected[marker] = source
                output.append(marker)
                position = math_end
                continue
            output.append("$$")
            position += 2
            continue

        is_inline_start = (
            content[position] == "$"
            and not _is_escaped(content, position)
            and (position == 0 or content[position - 1] != "$")
            and (position + 1 == len(content) or content[position + 1] != "$")
        )
        if is_inline_start:
            math_end = _find_inline_end(content, position + 1)
            if math_end is not None:
                math_end += 1
                source = content[position:math_end]
                marker = _placeholder(source)
                protected[marker] = source
                output.append(marker)
                position = math_end
                continue

        output.append(content[position])
        position += 1

    return "".join(output), protected


class DollarMathPreprocessor(Preprocessor):
    def __init__(self, md, extension: "DollarMathExtension"):
        super().__init__(md)
        self.extension = extension

    def run(self, lines: list[str]) -> list[str]:
        content, protected = protect_dollar_math("\n".join(lines))
        self.extension.protected.update(protected)
        return content.split("\n")


class DollarMathPostprocessor(Postprocessor):
    def __init__(self, md, extension: "DollarMathExtension"):
        super().__init__(md)
        self.extension = extension

    def run(self, text: str) -> str:
        for marker, source in self.extension.protected.items():
            text = text.replace(marker, html.escape(source, quote=False))
        return text


class DollarMathExtension(Extension):
    def __init__(self, **kwargs):
        self.protected: dict[str, str] = {}
        super().__init__(**kwargs)

    def reset(self) -> None:
        self.protected.clear()

    def extendMarkdown(self, md) -> None:
        md.preprocessors.register(
            DollarMathPreprocessor(md, self),
            "foliate_dollar_math",
            20,
        )
        md.postprocessors.register(
            DollarMathPostprocessor(md, self),
            "foliate_dollar_math",
            -5,
        )
        md.registerExtension(self)


def makeExtension(**kwargs) -> DollarMathExtension:  # noqa: N802
    return DollarMathExtension(**kwargs)
