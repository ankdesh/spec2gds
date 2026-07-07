"""Office-compatible archive support for `.spec` documents."""

import copy
import os
import shutil
import tempfile
import typing
import zipfile

import odfdo


class AgentSpecArchive:
    """Archive wrapper for `.spec` documents and embedded agent metadata.

    The current `.spec` implementation keeps the human-readable document body
    compatible with office-document tooling while exposing a project-owned
    `spec_data/` tree for structured payloads, graph metadata, and artifact
    references.
    """

    document: odfdo.Document
    custom_files: dict[str, bytes]
    container_path: typing.Optional[str]

    def __init__(self, path: typing.Optional[str] = None) -> None:
        """Load an existing `.spec` archive or create a blank document package."""
        self.custom_files = {}
        self.container_path = path

        if path is not None and os.path.exists(path) and os.path.getsize(path) > 0:
            try:
                self.document = odfdo.Document(path)
            except Exception as exc:
                raise IOError(f"Failed to load .spec document from {path}: {exc}") from exc

            try:
                self._load_custom_files()
            except Exception as exc:
                raise IOError(f"Failed to parse custom parts from .spec document: {exc}") from exc
        else:
            self.document = odfdo.Document.new("text")

    def _load_custom_files(self) -> None:
        """Populate the custom-file cache from package entries under `spec_data/`."""
        self.custom_files.clear()

        for part_name in self.document.get_parts():
            if not part_name.startswith("spec_data/"):
                continue
            part_content: typing.Any = self.document.get_part(part_name)

            if isinstance(part_content, bytes):
                content_bytes = part_content
            elif hasattr(part_content, "serialize"):
                content_bytes = typing.cast(bytes, part_content.serialize())
            elif hasattr(part_content, "bytes"):
                content_bytes = typing.cast(bytes, part_content.bytes)
            else:
                content_bytes = str(part_content).encode("utf-8")

            self.custom_files[part_name] = copy.deepcopy(content_bytes)

    def inject_file(self, full_path_in_container: str, content: bytes, media_type: str) -> None:
        """Store a custom payload and register it so office editors preserve it."""
        if not full_path_in_container.startswith("spec_data/"):
            raise ValueError("All custom files must reside in the 'spec_data/' sub-directory.")

        self.custom_files[full_path_in_container] = copy.deepcopy(content)
        self.document.set_part(full_path_in_container, content)

        manifest: typing.Any = self.document.get_part("META-INF/manifest.xml")
        if manifest is not None and hasattr(manifest, "add_full_path"):
            manifest.add_full_path(full_path_in_container, media_type)

    def extract_file(self, full_path_in_container: str) -> bytes:
        """Return a defensive copy of one custom payload from the archive cache."""
        if full_path_in_container not in self.custom_files:
            raise KeyError(f"File {full_path_in_container} does not exist in this archive.")
        return copy.deepcopy(self.custom_files[full_path_in_container])

    def delete_file(self, full_path_in_container: str) -> None:
        """Remove a custom payload from the archive and package manifest."""
        if full_path_in_container in self.custom_files:
            del self.custom_files[full_path_in_container]

        try:
            self.document.del_part(full_path_in_container)
        except Exception:
            pass

        manifest: typing.Any = self.document.get_part("META-INF/manifest.xml")
        if manifest is not None and hasattr(manifest, "del_full_path"):
            manifest.del_full_path(full_path_in_container)

    def save(self, path: typing.Optional[str] = None) -> None:
        """Save the archive and normalize the office-compatible package header."""
        if path is not None:
            save_target = path
        elif self.container_path is not None:
            save_target = self.container_path
        else:
            raise ValueError("No save target path specified.")

        try:
            self.document.save(save_target)
        except Exception as exc:
            raise IOError(f"Failed to write package to {save_target}: {exc}") from exc

        try:
            self._enforce_mimetype_integrity(save_target)
        except Exception as exc:
            raise IOError(f"Failed to post-process package mimetype alignment: {exc}") from exc

    def _enforce_mimetype_integrity(self, file_path: str) -> None:
        """Place the package mimetype first and uncompressed for editor compatibility."""
        temp_fd, temp_path = tempfile.mkstemp()
        os.close(temp_fd)

        try:
            shutil.copy2(file_path, temp_path)

            entries: dict[str, bytes] = {}
            with zipfile.ZipFile(temp_path, "r") as z_read:
                for name in z_read.namelist():
                    if name != "mimetype":
                        entries[name] = z_read.read(name)

            with zipfile.ZipFile(file_path, "w") as z_write:
                z_write.writestr(
                    "mimetype",
                    b"application/vnd.oasis.opendocument.text",
                    compress_type=zipfile.ZIP_STORED,
                )
                for name, data in entries.items():
                    z_write.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
