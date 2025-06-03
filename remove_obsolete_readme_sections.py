import re
import os

readme_file_path = "README.md"

try:
    with open(readme_file_path, "r", encoding="utf-8") as f:
        content = f.read()
except FileNotFoundError:
    print(f"ERROR: {readme_file_path} not found. Cannot proceed.")
    exit(1)

# Helper function to remove a section by its header
def remove_section(text, header_start_pattern_str, next_header_level_char="#"):
    # header_start_pattern_str is the string for the header, e.g., r"\n## 📏 Architecture"
    # We need to determine the level for the 'next_header_pattern'

    match = re.search(header_start_pattern_str, text, re.MULTILINE)
    if not match:
        print(f"Section starting with pattern '{header_start_pattern_str}' not found for removal.")
        return text

    section_start_index = match.start()

    # Determine the level of the header we are trying to remove based on number of '#'
    header_level = 0
    header_match_for_level = re.match(r"\n(#+)\s", header_start_pattern_str) # Match \n## Header (example)
    if header_match_for_level:
        header_level = len(header_match_for_level.group(1))

    # Find the next header that is of the same or higher level, or end of text
    next_header_regex_str = r"\n" + next_header_level_char + ("{1," + str(header_level) + r"}[^#\s]") if header_level > 0 else r"\n#"

    next_section_match = None
    if match.end() < len(text): # Search from the end of the current header's match
        next_section_match = re.search(next_header_regex_str, text[match.end():], re.MULTILINE)

    if next_section_match:
        section_end_index = match.end() + next_section_match.start()
        print(f"Removing section from '{text[section_start_index : section_start_index + min(70, len(text)-section_start_index)].strip().splitlines()[0]}...'")
        return text[:section_start_index] + text[section_end_index:]
    else:
        print(f"Removing section from '{text[section_start_index : section_start_index + min(70, len(text)-section_start_index)].strip().splitlines()[0]}...' to end of file.")
        return text[:section_start_index]

# --- Sections and content to remove ---

# 1. Remove old components list under "It is built on a modular design..."
marker_start_old_components = "It is built on a modular design and currently supports the following components:"
# The ADK architecture section should directly follow this line after cleanup.
marker_end_old_components = "## 🧬 System Architecture (ADK-based Refactor)"
pos_start = content.find(marker_start_old_components)
pos_end = content.find(marker_end_old_components)

if pos_start != -1 and pos_end != -1 and pos_start < pos_end:
    text_between_markers = content[pos_start + len(marker_start_old_components) : pos_end]
    # Check if what we are removing contains the old structure
    if "### Database Connectors" in text_between_markers and "### Agents " in text_between_markers:
        content = content[:pos_start + len(marker_start_old_components)] + "\n\n" + content[pos_end:]
        print("Old components list (DB Connectors, Vector Stores, Agents) removed.")
    else:
        print("WARN: Could not confirm structure of old components list for removal. Skipping this part, or structure already changed.")
elif pos_start != -1 and pos_end != -1 and pos_start > pos_end:
    print(f"WARN: Start marker '{marker_start_old_components}' found after end marker '{marker_end_old_components}'. Skipping removal of old components.")
else:
    print("WARN: Markers for old components list not found. Skipping removal, or already removed.")


# 2. Remove old "📏 Architecture" section
content = remove_section(content, r"\n## 📏 Architecture") # H2 level

# 3. Remove old "🧬 Repository Structure" section
content = remove_section(content, r"\n## 🧬 Repository Structure") # H2 level

# 4. Remove "🏁 Getting Started: Main Repository"
# This is a H1 level based on its style in the original README (no #, but prominent)
# The helper function might not work directly. Manual removal based on start and next known major header.
getting_started_main_repo_header = "🏁 Getting Started: Main Repository"
gs_start_pos = content.find(getting_started_main_repo_header)
if gs_start_pos != -1:
    # Find a suitable end point: either next major emoji header or next H2/H1
    next_header_match = re.search(r"\n(## |### |🏁 |✨ |📏 |🧬 |🖥️ |📗 |🧹 |🚧 |🪪 |🧪 |🙋 )", content[gs_start_pos + len(getting_started_main_repo_header):])
    if next_header_match:
        gs_end_pos = gs_start_pos + len(getting_started_main_repo_header) + next_header_match.start()
        # Safety check: ensure we are not deleting newly added ADK sections by mistake
        text_to_be_deleted = content[gs_start_pos:gs_end_pos]
        if "## 🧬 System Architecture (ADK-based Refactor)" in text_to_be_deleted or \
           "## 🚀 Running the Example (ADK-based Refactor)" in text_to_be_deleted:
            print(f"WARN: Removal of '{getting_started_main_repo_header}' seems to overlap with new ADK sections. Skipping.")
        else:
            content = content[:gs_start_pos] + content[gs_end_pos:]
            print(f"Section '{getting_started_main_repo_header}' removed.")
    else:
        # If no clear next header, it might be the last section before something like "Build angular frontend"
        angular_frontend_marker = "🖥️ Build a angular based frontend for this solution"
        angular_pos = content.find(angular_frontend_marker, gs_start_pos)
        if angular_pos != -1:
             content = content[:gs_start_pos] + content[angular_pos:]
             print(f"Section '{getting_started_main_repo_header}' removed (ended before Angular Frontend).")
        else:
            print(f"WARN: Could not determine clear end for '{getting_started_main_repo_header}'. Skipping removal to be safe.")
else:
    print(f"Section '{getting_started_main_repo_header}' not found.")

# 5. Remove "🖥️ Build a angular based frontend for this solution"
angular_frontend_header = "🖥️ Build a angular based frontend for this solution"
angular_start_pos = content.find(angular_frontend_header)
if angular_start_pos != -1:
    next_header_match = re.search(r"\n(## |### |🏁 |✨ |📏 |🧬 |🖥️ |📗 |🧹 |🚧 |🪪 |🧪 |🙋 )", content[angular_start_pos + len(angular_frontend_header):])
    if next_header_match:
        angular_end_pos = angular_start_pos + len(angular_frontend_header) + next_header_match.start()
        content = content[:angular_start_pos] + content[angular_end_pos:]
        print(f"Section '{angular_frontend_header}' removed.")
    else: # Might be the last content block before FAQs or similar
        faqs_marker = "📗 FAQs and Best Practices"
        faqs_pos = content.find(faqs_marker, angular_start_pos)
        if faqs_pos != -1:
            content = content[:angular_start_pos] + content[faqs_pos:]
            print(f"Section '{angular_frontend_header}' removed (ended before FAQs).")
        else: # If truly last, remove to end.
            content = content[:angular_start_pos]
            print(f"Section '{angular_frontend_header}' removed (to end of file).")
else:
    print(f"Section '{angular_frontend_header}' not found.")

# 6. Remove "🧹 CleanUp Resources"
content = remove_section(content, r"\n## 🧹 CleanUp Resources") # H2 Level

# 7. Remove specific old documentation links if "📄 Documentation" section exists
doc_section_header = "📄 Documentation"
doc_section_pos = content.find(doc_section_header)
if doc_section_pos != -1:
    # Define the end of the documentation section (e.g., start of next major section or H1/H2)
    next_major_header_after_doc_match = re.search(r"\n(# |## |🚧 )", content[doc_section_pos + len(doc_section_header):])
    doc_section_end_pos = -1
    if next_major_header_after_doc_match:
        doc_section_end_pos = doc_section_pos + len(doc_section_header) + next_major_header_after_doc_match.start()

    doc_section_text = content[doc_section_pos : doc_section_end_pos if doc_section_end_pos != -1 else len(content)]

    original_doc_section_text = str(doc_section_text)

    doc_section_text = re.sub(r"\* \[`Architecture`\]\(/docs/architecture.md\)\n?", "", doc_section_text)
    doc_section_text = re.sub(r"\* \[`FAQ`\]\(/docs/faq.md\)\n?", "", doc_section_text)
    doc_section_text = re.sub(r"\* \[`Best Practice doc`\]\(/docs/best_practices.md\)\n?", "", doc_section_text)

    if original_doc_section_text != doc_section_text:
        print("Specific old documentation links removed from '📄 Documentation' section.")
        if doc_section_end_pos != -1:
            content = content[:doc_section_pos] + doc_section_text + content[doc_section_end_pos:]
        else:
            content = content[:doc_section_pos] + doc_section_text
    else:
        print("No specific old documentation links found in '📄 Documentation' or section structure changed.")
else:
    print("'📄 Documentation' section header not found, skipping link removal.")


# 8. Remove "Note: the library was formerly named Talk2Data..."
# This note might be near the old "Agents" list or near the "Overview"
content = re.sub(r"\n\*\*Note:\*\* the library was formerly named Talk2Data.*?in this repository\.\s*\n", "\n", content, flags=re.DOTALL)
print("Talk2Data note removed (if found).")


# Ensure there are not excessive newlines from removals
content = re.sub(r"\n{3,}", "\n\n", content)


with open(readme_file_path, "w", encoding="utf-8") as f:
    f.write(content.strip() + "\n") # Add a single trailing newline

print(f"README.md cleanup script completed.")
