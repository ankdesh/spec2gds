import copy
import io
import os
import shutil
import tempfile
import typing
import zipfile
import odfdo
import lxml.etree as etree

class HybridODTContainer:
    """
    Core container engine bridging high-level ODF/odfdo document APIs
    and low-level ZIP packaging with uncompressed mimetype enforcement.
    
    This class wraps odfdo's document object model and provides low-level ZIP 
    manifest and mimetype alignments. It maintains compatibility with standard 
    editors like LibreOffice Writer while enabling custom spec data embedding.
    """
    # Pre-declared typed instance attributes (Mojo compatibility)
    document: odfdo.Document
    custom_files: dict[str, bytes]
    container_path: typing.Optional[str]

    def __init__(self, path: typing.Optional[str] = None) -> None:
        """
        Initialize the hybrid ODT container.
        
        Args:
            path: Optional string path to an existing hybrid ODT file.
                  If the file exists and is not empty, it will be loaded.
                  Otherwise, a new blank text ODT document is initialized.
        """
        # Cache of custom files residing in the 'spec_data/' directory of the ZIP
        self.custom_files = {}
        # Track the active file system path of this container for saving later
        self.container_path = path

        # Check if we should load an existing ODT file. We strictly verify 
        # that the file exists and has size > 0 to prevent odfdo from crashing
        # on empty/0-byte placeholder files created by tempfile utilities.
        if path is not None and os.path.exists(path) and os.path.getsize(path) > 0:
            # 1. Load the ODT zip structure via odfdo
            try:
                self.document = odfdo.Document(path)
            except Exception as e:
                # Isolate exception flow to prevent raw trace leaks (Mojo guideline)
                raise IOError(f"Failed to load ODT document from {path}: {e}")

            # 2. Parse the underlying zip files and populate the custom files cache
            try:
                self._load_custom_files()
            except Exception as e:
                raise IOError(f"Failed to parse custom parts from ODT: {e}")
        else:
            # Create a pristine new ODF text document from odfdo's template
            self.document = odfdo.Document.new("text")

    def _load_custom_files(self) -> None:
        """
        Scan all parts inside the ODF document package and pull files 
        that reside under the 'spec_data/' directory into our cache.
        """
        self.custom_files.clear()
        
        # odfdo stores all ZIP entries as separate 'parts'.
        parts_list: list[str] = self.document.get_parts()
        for part_name in parts_list:
            # Custom hardware specifications are kept strictly isolated under 'spec_data/'
            if part_name.startswith("spec_data/"):
                part_content: typing.Any = self.document.get_part(part_name)
                
                # Extract raw bytes depending on part object type returned by odfdo
                content_bytes: bytes = b""
                if isinstance(part_content, bytes):
                    content_bytes = part_content
                elif hasattr(part_content, "serialize"):
                    # XML parts (e.g. meta, content, styles) are objects and must be serialized
                    content_bytes = typing.cast(bytes, part_content.serialize())
                elif hasattr(part_content, "bytes"):
                    content_bytes = typing.cast(bytes, part_content.bytes)
                else:
                    content_bytes = str(part_content).encode("utf-8")

                # Conform to value semantics: store an isolated deep copy in the cache
                # to prevent cross-scope mutability leakage during compiler migrations.
                self.custom_files[part_name] = copy.deepcopy(content_bytes)

    def inject_file(self, full_path_in_container: str, content: bytes, media_type: str) -> None:
        """
        Inject a raw custom data payload into the container ZIP and register it in manifest.xml.
        
        Args:
            full_path_in_container: Relative ZIP path, must start with 'spec_data/'.
            content: Raw bytes representation of the data payload.
            media_type: MIME type description (e.g., 'application/x-spec-json').
        """
        if not full_path_in_container.startswith("spec_data/"):
            raise ValueError("All custom files must reside in the 'spec_data/' sub-directory.")

        # Cache a deep copy to enforce strict value boundary isolation
        self.custom_files[full_path_in_container] = copy.deepcopy(content)

        # Write/Update the part directly inside odfdo's memory package
        self.document.set_part(full_path_in_container, content)

        # Synchronize manifest.xml (located at META-INF/manifest.xml).
        # Standard office editors (like LibreOffice Writer) will silently delete 
        # unregistered custom files on save because they treat them as corruption.
        # Adding them to the manifest tells the editors to preserve them as opaque blobs.
        manifest: typing.Any = self.document.get_part("META-INF/manifest.xml")
        if manifest is not None and hasattr(manifest, "add_full_path"):
            manifest.add_full_path(full_path_in_container, media_type)

    def extract_file(self, full_path_in_container: str) -> bytes:
        """
        Extract custom data file content from the container cache.
        
        Args:
            full_path_in_container: Absolute path within container ZIP (starts with 'spec_data/').
            
        Returns:
            Decoupled deep copy of the raw bytes of the file.
        """
        if full_path_in_container not in self.custom_files:
            raise KeyError(f"File {full_path_in_container} does not exist in this container.")
        
        # Enforce strict value copy semantics on extraction boundary
        return copy.deepcopy(self.custom_files[full_path_in_container])

    def delete_file(self, full_path_in_container: str) -> None:
        """
        Remove custom data file from the cache, document parts list, and manifest.xml registry.
        
        Args:
            full_path_in_container: Absolute path within container ZIP to delete.
        """
        # 1. Remove from local memory cache
        if full_path_in_container in self.custom_files:
            del self.custom_files[full_path_in_container]

        # 2. Delete from odfdo's internal memory parts list
        try:
            self.document.del_part(full_path_in_container)
        except Exception:
            pass

        # 3. Clean up the manifest registry entry to avoid pointing to dangling paths
        manifest: typing.Any = self.document.get_part("META-INF/manifest.xml")
        if manifest is not None and hasattr(manifest, "del_full_path"):
            manifest.del_full_path(full_path_in_container)

    def save(self, path: typing.Optional[str] = None) -> None:
        """
        Save the hybrid container package to disk and apply uncompressed mimetype post-processing.
        
        Args:
            path: Optional output path. If omitted, uses self.container_path.
        """
        save_target: str = ""
        if path is not None:
            save_target = path
        elif self.container_path is not None:
            save_target = self.container_path
        else:
            raise ValueError("No save target path specified.")

        # 1. Serialize and write the document package via odfdo
        try:
            self.document.save(save_target)
        except Exception as e:
            raise IOError(f"Failed to write package to {save_target}: {e}")

        # 2. Run post-processing to align zip layout with ODF standard magic rules
        try:
            self._enforce_mimetype_integrity(save_target)
        except Exception as e:
            raise IOError(f"Failed to post-process package mimetype alignment: {e}")

    def _enforce_mimetype_integrity(self, file_path: str) -> None:
        """
        Force 'mimetype' to be stored completely uncompressed and placed as the 
        absolute first file entry in the ZIP archive.
        
        This satisfies the strict ODF standard requirement (ISO/IEC 26300) where 
        the magic number string must sit exactly at byte position 38 so that OS 
        mimetype detection libraries can read the file without full ZIP decompression.
        """
        temp_fd: int
        temp_path: str
        temp_fd, temp_path = tempfile.mkstemp()
        os.close(temp_fd)

        try:
            # Create a safe temp copy of the newly saved package
            shutil.copy2(file_path, temp_path)
            
            # Read all existing ZIP entries (skipping the potentially misaligned mimetype)
            entries: dict[str, bytes] = {}
            with zipfile.ZipFile(temp_path, "r") as z_read:
                for name in z_read.namelist():
                    if name != "mimetype":
                        entries[name] = z_read.read(name)
            
            # Re-write the ZIP file from scratch to guarantee entry ordering
            with zipfile.ZipFile(file_path, "w") as z_write:
                # 1. Write 'mimetype' uncompressed first to place it at the beginning
                z_write.writestr(
                    "mimetype",
                    b"application/vnd.oasis.opendocument.text",
                    compress_type=zipfile.ZIP_STORED
                )
                # 2. Write all other package files compressed (deflated)
                for name, data in entries.items():
                    z_write.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)
        finally:
            # Cleanup temp file securely
            if os.path.exists(temp_path):
                os.remove(temp_path)
