import os
import tempfile
import zipfile
import spec2gds.agent_spec.package.archive as container

def test_container_instantiation() -> None:
    """Test creating a new container."""
    cont = container.AgentSpecArchive()
    if cont.document is None:
        raise AssertionError("Container document was not initialized.")
    if len(cont.custom_files) != 0:
        raise AssertionError("New container should not have custom files cached.")

def test_file_injection_and_extraction() -> None:
    """Test injecting and extracting custom files with media type registration."""
    cont = container.AgentSpecArchive()
    
    file_path = "spec_data/simple-json/test.json"
    content = b'{"name": "test"}'
    mtype = "application/x-spec-json"
    
    cont.inject_file(file_path, content, mtype)
    
    # 1. Verify cached in dictionary
    if file_path not in cont.custom_files:
        raise AssertionError("Injected file was not cached in custom_files dict.")
        
    # 2. Extract and verify content
    extracted = cont.extract_file(file_path)
    if extracted != content:
        raise AssertionError(f"Expected content {content}, got {extracted}")
        
    # 3. Verify manifest contains entry
    manifest = cont.document.get_part("META-INF/manifest.xml")
    if manifest is None or not hasattr(manifest, "get_paths"):
        raise AssertionError("manifest.xml part not found or unsupported.")
    if file_path not in manifest.get_paths():
        raise AssertionError("Injected file path was not registered in manifest.")
    if manifest.get_media_type(file_path) != mtype:
        raise AssertionError("Injected file has incorrect registered media-type.")

def test_file_deletion() -> None:
    """Test deleting custom files from container."""
    cont = container.AgentSpecArchive()
    
    file_path = "spec_data/simple-json/test.json"
    content = b'{"name": "test"}'
    mtype = "application/x-spec-json"
    
    cont.inject_file(file_path, content, mtype)
    cont.delete_file(file_path)
    
    if file_path in cont.custom_files:
        raise AssertionError("Deleted file was not removed from custom_files cache.")
        
    manifest = cont.document.get_part("META-INF/manifest.xml")
    if file_path in manifest.get_paths():
        raise AssertionError("Deleted file path was not removed from manifest.")

def test_mimetype_and_zip_integrity() -> None:
    """Test that saved ZIP has uncompressed mimetype as the first entry."""
    cont = container.AgentSpecArchive()
    
    temp_fd, temp_path = tempfile.mkstemp(suffix=".spec")
    os.close(temp_fd)
    
    try:
        cont.save(temp_path)
        
        # Open raw zip and inspect entries
        with zipfile.ZipFile(temp_path, "r") as z:
            namelist = z.namelist()
            if not namelist:
                raise AssertionError("Saved ZIP is empty.")
            
            # Check uncompressed first entry constraint
            first_entry = namelist[0]
            if first_entry != "mimetype":
                raise AssertionError(f"Expected first ZIP entry to be 'mimetype', got: '{first_entry}'")
                
            info = z.getinfo("mimetype")
            if info.compress_type != zipfile.ZIP_STORED:
                raise AssertionError("mimetype entry was compressed. Must be stored uncompressed.")
                
            # Verify magic number bytes
            magic = z.read("mimetype")
            if magic != b"application/vnd.oasis.opendocument.text":
                raise AssertionError(f"Invalid mimetype magic bytes: {magic}")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
