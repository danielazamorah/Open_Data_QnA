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
def remove_h2_section_robust(text, section_title_pattern):
    escaped_title = re.escape(section_title_pattern)
    regex = r"\n## " + escaped_title + r"\n(?:.|\n)*?(?=\n(?:##?#? )|\Z)"
    new_text, count = re.subn(regex, "", text, flags=re.MULTILINE)
    if count > 0:
        print(f"Removed section matching H2 title: '{section_title_pattern}' ({count} instance(s)).")
    return new_text

# --- 1. Modify "Key Features" ---
key_features_marker = "\n**Key Features:**\n"
new_key_features_list = [
    "* **Conversational Querying with Multiturn Support:** Ask questions naturally, without requiring SQL knowledge and ask follow up questions (supported via persistent memory in the ADK version).",
    "* **Table Grouping (`user_grouping`):** Group tables under a use-case or user grouping name to help focus context for the LLMs.",
    "* **Multi Schema/Dataset Support:** Conceptually supported via `user_grouping` to combine tables from different schemas/datasets.",
    "* **SQL Generation:** Automatically generates SQL queries based on your questions using ADK agents.",
    "* **Query Refinement:** Includes an `SQLValidatorAgent` for validating queries.",
    "* **Natural Language Responses:** Presents query results in clear, easy-to-understand language via an ADK agent.",
    "* **Extensible:** The ADK framework promotes modularity for customization and integration."
]
new_key_features_section_text = key_features_marker + "\n".join(new_key_features_list) + "\n"

key_features_start_pos = content.find(key_features_marker)
if key_features_start_pos != -1:
    old_list_end_marker = "\nIt is built on a modular design and currently supports the following components:"
    old_list_end_marker_alt = "\n## 🧬 System Architecture (ADK-based Refactor)"

    old_list_end_pos = content.find(old_list_end_marker, key_features_start_pos)
    if old_list_end_pos == -1:
        old_list_end_pos = content.find(old_list_end_marker_alt, key_features_start_pos)

    if old_list_end_pos != -1:
        content = content[:key_features_start_pos] + new_key_features_section_text + content[old_list_end_pos:]
        print("Key Features section updated for ADK relevance.")
    else:
        print("WARN: Could not precisely find end of old Key Features list. Update skipped to avoid malforming README.")
else:
    print("WARN: Key Features section marker not found. Update skipped.")

# --- 2. Targeted Removals of Specific Obsolete Snippets ---

old_components_header = "It is built on a modular design and currently supports the following components:"
adk_arch_header = "## 🧬 System Architecture (ADK-based Refactor)"
start_pos_oc = content.find(old_components_header)
end_pos_oc = content.find(adk_arch_header)

if start_pos_oc != -1 and end_pos_oc != -1 and start_pos_oc < end_pos_oc:
    content_between = content[start_pos_oc + len(old_components_header) : end_pos_oc]
    if "### Database Connectors" in content_between or "### Agents " in content_between or "### Vector Stores" in content_between:
        content = content[:start_pos_oc + len(old_components_header)] + "\n\n" + content[end_pos_oc:]
        print("Cleaned up old components list between '...following components:' and ADK Architecture header.")

content = remove_h2_section_robust(content, "📏 Architecture")
content = remove_h2_section_robust(content, "🧬 Repository Structure")
content = remove_h2_section_robust(content, "🧹 CleanUp Resources")

jupyter_approach_header = "### A) Jupyter Notebook Based Approach"
jupyter_start_pos = content.find(jupyter_approach_header)
if jupyter_start_pos != -1:
    next_cli_approach = content.find("### B) Command Line Interface (CLI) Based Approach", jupyter_start_pos)
    if next_cli_approach != -1 :
         content = content[:jupyter_start_pos] + content[next_cli_approach:]
         print(f"Section '{jupyter_approach_header}' removed (ended before CLI approach).")
    else:
        # If B) is not found, this might be part of a larger section that was removed, or it's structured differently.
        # A simple way to ensure it's gone if it exists as a standalone block before next H2 or major emoji:
        next_major_header_match_jupyter = re.search(r"\n(## |🏁 |✨ |📏 |🧬 |🖥️ |📗 |🧹 |🚧 |🪪 |🧪 |🙋 )", content[jupyter_start_pos + len(jupyter_approach_header):])
        if next_major_header_match_jupyter:
            jupyter_end_pos = jupyter_start_pos + len(jupyter_approach_header) + next_major_header_match_jupyter.start()
            content = content[:jupyter_start_pos] + content[jupyter_end_pos:]
            print(f"Section '{jupyter_approach_header}' removed (heuristic end).")
        else:
            # If it's potentially the last thing in a "Getting Started" that should have been removed,
            # this is harder to clean safely without over-deleting.
            # For now, if the specific "B) CLI" marker isn't there, we'll assume it might be part of a larger deleted block
            # or the structure is too ambiguous for this specific regex.
            print(f"WARN: '{jupyter_approach_header}' found, but '### B) Command Line Interface (CLI) Based Approach' not found after it. Manual check advised if it's still visible.")


if jupyter_approach_header not in content: # Re-check after attempted removal
    print(f"'{jupyter_approach_header}' seems removed or was not present initially.")


cli_instruction_pattern = r"```bash\npython opendataqna.py --session_id.*?```"
content, count = re.subn(cli_instruction_pattern, "", content, flags=re.DOTALL)
if count > 0:
    print(f"Old CLI instruction block for 'opendataqna.py --session_id' removed ({count} instance(s)).")

# --- 3. Correct Typo ---
content = content.replace("Natural Language Responses:** DRun queries", "Natural Language Responses:** Run queries")
if "DRun queries" not in content:
    print("Typo 'DRun' corrected.")

# Clean up excessive newlines again
content = re.sub(r"\n{3,}", "\n\n", content)
content = content.strip() + "\n"

with open(readme_file_path, "w", encoding="utf-8") as f:
    f.write(content)

print(f"README.md refinement script completed.")
