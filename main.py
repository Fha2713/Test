"""IFS Language Automation Tool - main entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional

from lng_generator import LNGGenerator
from logger import IFSLogger
from parser import IFSXMLParser
from translator import IFSTranslator
from trs_generator import TRSGenerator
from validator import IFSValidator


class IFSLanguageAutomation:
    """Orchestrate parsing, ID filtering, merging, translation and validation."""

    def __init__(
        self,
        xml_path: str,
        output_dir: Optional[str] = None,
        languages: Optional[List[str]] = None,
        translation_backend: str = "dictionary",
        api_key: Optional[str] = None,
    ):
        self.xml_path = Path(xml_path)
        self.output_dir = Path(output_dir) if output_dir else self.xml_path.parent
        self.languages = languages or ["sv-SE", "nb-NO"]
        self.logger = IFSLogger(self.output_dir / "Log.txt")
        self.parser = IFSXMLParser(self.xml_path)
        self.translator = IFSTranslator(
            backend=translation_backend,
            api_key=api_key,
            dictionary_dir=self.xml_path.parent,
        )
        self.validator = IFSValidator()
        self.parsed_data: Dict = {}
        self.custom_data: Dict = {}
        self.lng_data: Dict = {}
        self.translations: Dict[str, Dict[str, str]] = {}
        self.lng_output_path: Optional[Path] = None
        self.trs_output_paths: Dict[str, Path] = {}

    @property
    def main_type(self) -> str:
        return self.custom_data.get("main_type") or self.custom_data.get("type") or "LU"

    @property
    def sub_type(self) -> str:
        return self.custom_data.get("sub_type") or (
            "All" if self.main_type.upper() == "WEB" else "Logical Unit"
        )

    def run(self) -> None:
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            self.logger.info("=" * 60)
            self.logger.info("IFS Language Automation Tool - Starting")
            self.logger.info("=" * 60)
            self._parse_xml()
            self._extract_custom_resources()

            if not self.custom_data.get("resources"):
                self.logger.info(
                    f"No custom ID prefixes (C/C_/DM/CDM) found in {self.xml_path}; skipping generation."
                )
            else:
                self._generate_lng_file()
                self._translate_labels()
                self._generate_trs_files()
                self._validate_files()

            self.logger.info("=" * 60)
            self.logger.info("IFS Language Automation Tool - Completed Successfully")
            self.logger.info("=" * 60)
            self.logger.write_to_file()
            print("\n" + "=" * 60)
            print("SUCCESS: All files generated and validated")
            print("=" * 60)
            print(f"\nGenerated files in: {self.output_dir}")
            print(self.logger.get_summary())
        except Exception as exc:
            self.logger.error(f"Fatal error: {exc}")
            self.logger.write_to_file()
            print(f"\nERROR: {exc}")
            raise

    def _parse_xml(self) -> None:
        self.logger.log_parsing_start(str(self.xml_path))
        if not self.xml_path.exists():
            raise FileNotFoundError(f"XML file not found: {self.xml_path}")
        self.parsed_data = self.parser.parse()
        stats = self.parser.get_statistics(self.parsed_data)
        self.logger.info(
            f"XML parsing complete: type={self.parsed_data['type']}, "
            f"top-level={stats['total_logical_units']}, resources={stats['total_resources']}, "
            f"text resources={stats['text_resources']}"
        )

    def _extract_custom_resources(self) -> None:
        self.logger.info("Filtering custom resources by XML ID (C/C_/DM/CDM, case-aware)")
        self.custom_data = self.parser.extract_custom_resources(self.parsed_data)
        text_nodes = list(self.parser.iter_text_nodes(self.custom_data))
        for node in text_nodes:
            self.logger.log_field_processed(node.get("id") or node.get("cs_key", ""), node["label"])
        self.logger.success(
            f"Retained {len(self.custom_data.get('resources', []))} top-level resource(s) "
            f"and {len(text_nodes)} text entry/entries"
        )

    def _generate_lng_file(self) -> None:
        generator = LNGGenerator(
            self.custom_data["module"],
            self.custom_data["layer"],
            self.main_type,
            self.sub_type,
        )
        default_path = self.output_dir / generator.get_file_name(
            self.custom_data["module"], self.custom_data["layer"]
        )
        existing_path = self._find_matching_file(".lng", language=None, preferred=default_path)
        output_path = existing_path or default_path

        if existing_path:
            self.logger.info(f"Merging matching existing .lng file: {existing_path.name}")
            self.lng_data = generator.merge_with_existing(self.custom_data, str(existing_path))
            action = "Updated"
        else:
            self.logger.info(f"Generating new .lng file: {output_path.name}")
            self.lng_data = self.custom_data
            action = "Created"

        self.lng_output_path = Path(generator.generate_file(self.lng_data, str(output_path)))
        self.logger.log_file_generation(str(self.lng_output_path), action)

    def _translate_labels(self) -> None:
        labels = sorted(
            {
                node["label"]
                for node in self.parser.iter_text_nodes(self.custom_data, translations_only=True)
                if node.get("label")
            }
        )
        for language in self.languages:
            self.logger.log_translation_start(language, len(labels))
            self.translations[language] = self.translator.translate_batch(labels, language)
            self.logger.log_translation_complete(language)

    def _generate_trs_files(self) -> None:
        for language in self.languages:
            generator = TRSGenerator(
                self.custom_data["module"],
                self.custom_data["layer"],
                language,
                self.main_type,
                self.sub_type,
            )
            default_path = self.output_dir / generator.get_file_name(
                self.custom_data["module"], self.custom_data["layer"], language
            )
            existing_path = self._find_matching_file(
                ".trs", language=language, preferred=default_path
            )
            output_path = existing_path or default_path
            action = "Updated" if existing_path else "Created"
            if existing_path:
                self.logger.info(f"Preserving translations from: {existing_path.name}")
            generated = generator.generate_file(
                self.custom_data,
                self.translations[language],
                str(output_path),
                existing_file=str(existing_path) if existing_path else None,
            )
            self.trs_output_paths[language] = Path(generated)
            self.logger.log_file_generation(generated, action)

    def _find_matching_file(
        self,
        suffix: str,
        language: Optional[str],
        preferred: Path,
    ) -> Optional[Path]:
        if preferred.exists():
            return preferred

        candidates: List[Path] = []
        for path in sorted(self.output_dir.glob(f"*{suffix}")):
            header = LNGGenerator.read_header(path)
            if header.get("Module", "").casefold() != self.custom_data["module"].casefold():
                continue
            if header.get("Layer", "").casefold() != self.custom_data["layer"].casefold():
                continue
            if header.get("Main Type", "").casefold() != self.main_type.casefold():
                continue
            if language and header.get("Culture", "").casefold() != language.casefold():
                continue
            candidates.append(path)

        if len(candidates) > 1:
            names = ", ".join(path.name for path in candidates)
            raise ValueError(
                f"Multiple matching existing {suffix} files found for module/layer/main type: {names}"
            )
        return candidates[0] if candidates else None

    def _validate_files(self) -> None:
        paths = [self.lng_output_path] + list(self.trs_output_paths.values())
        for path in paths:
            if path is None:
                continue
            self.logger.log_validation_start(str(path))
            valid, errors, warnings = self.validator.validate_file(str(path))
            for warning in warnings:
                self.logger.warning(warning)
            if not valid:
                for error in errors:
                    self.logger.error(error)
                raise ValueError(f"Validation failed for {path.name}")
            self.logger.log_validation_success(str(path))


def main() -> None:
    argument_parser = argparse.ArgumentParser(
        description="Generate/merge IFS .lng and .trs files from TranslatableResources XML"
    )
    argument_parser.add_argument("--xml", nargs="+", required=True, metavar="XML")
    argument_parser.add_argument("--output-dir")
    argument_parser.add_argument("--languages", default="sv-SE,nb-NO")
    argument_parser.add_argument(
        "--backend", choices=["dictionary", "groq", "google"], default="dictionary"
    )
    argument_parser.add_argument("--api-key")
    args = argument_parser.parse_args()

    languages = [item.strip() for item in args.languages.split(",") if item.strip()]
    xml_paths = [Path(item) for item in args.xml if str(item).lower().endswith(".xml")]
    if not xml_paths:
        print("No XML files to process.")
        return

    for xml_path in xml_paths:
        automation = IFSLanguageAutomation(
            xml_path=str(xml_path),
            output_dir=args.output_dir,
            languages=languages,
            translation_backend=args.backend,
            api_key=args.api_key,
        )
        try:
            automation.run()
        except Exception:
            sys.exit(1)


if __name__ == "__main__":
    main()
