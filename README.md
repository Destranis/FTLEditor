# FTL Translator

A graphical desktop application built with Python and wxPython to assist in the translation of `.ftl` (Fluent Translation List) files. It provides a side-by-side view of original and translated text, status tracking for translation progress, and integration with a simple JSON-based translation dictionary.

## Features

*   **Load and Save `.ftl` Files:** Open existing `.ftl` files or create new ones. Save translations back to `.ftl` format.
*   **Preserves File Structure:** Maintains comments, blank lines, and section markers (`##`, `--`) from the original `.ftl` file when saving.
*   **Side-by-Side Translation:** Displays the original text and the translation input field together for easy comparison.
*   **Key List:** Shows all translatable keys from the `.ftl` file in a listbox.
*   **Status Tracking & Sorting:**
    *   Each key is marked with a status:
        *   `(not translated)`: The translation field is empty.
        *   `(error: ...)`: A potential issue is detected (currently checks for mismatched ending punctuation like `.`, `!`, `?`, `:`). Provides details on the mismatch.
        *   `(done)`: The key has a translation and passes basic checks.
    *   The key list is automatically sorted primarily by status (Errors first, then Untranslated, then Done) and secondarily alphabetically by key name.
*   **Translation Dictionary:**
    *   Load an external dictionary from a JSON file (format: `{"source text": "translation text", ...}`).
    *   Save the current dictionary data to a JSON file.
    *   Look up selected original text (or the entire original value) in the loaded dictionary.
    *   Add new terms (original/translation pairs) to the dictionary directly from the application.
    *   Context menu option on the key list for dictionary lookup.
*   **Target Language Setting:** Specify the target language name (mainly for user reference, displayed in the status bar).
*   **Recent Files:** Keeps track of recently opened `.ftl` files for quick access.
*   **Unsaved Changes Prompt:** Warns the user before closing the application or opening a new file if there are unsaved changes.
*   **Basic Accessibility:** Includes accessible names for some UI controls.

## Usage

1.  **Run the Application:**
    ```2.  **Open an FTL File:** Go to `File` > `Open...` and select the `.ftl` file you want to translate. Recently opened files can be accessed via `File` > `Recent Files`.
3.  **Load a Dictionary (Optional):** Go to `Dictionary` > `Load Dictionary...` and select your JSON dictionary file.
4.  **Select a Key:** Click on a key in the listbox on the left panel. The key name, original value, and current translation (if any) will appear in the right panel.
5.  **Enter Translation:** Type or paste the translation into the "Translation" text area.
    *   As you type, the status in the listbox for that key will update dynamically (e.g., from `(not translated)` to `(done)` or `(error: ...)`). The list will re-sort if the status category changes.
    *   The detailed status is shown below the translation text area.
6.  **Use Dictionary Lookup (Optional):**
    *   With a key selected and a dictionary loaded, click the "Lookup in Dictionary" button.
    *   Alternatively, select specific text within the "Original Value" field and click the button (or right-click the key in the list and choose "Lookup in Dictionary").
    *   If the source text is found in the dictionary, a dialog will show the translation and ask if you want to insert it into the "Translation" field.
7.  **Add to Dictionary (Optional):** With a key selected and text in both "Original Value" and "Translation", go to `Dictionary` > `Add Term to Dictionary...` to add or update the entry in the internal dictionary data.
8.  **Save Changes:**
    *   `File` > `Save` (Ctrl+S): Saves changes to the currently opened file. Enabled only when changes are made.
    *   `File` > `Save As...`: Saves the current translations to a new or different `.ftl` file.
9.  **Save Dictionary (Optional):**
    *   `Dictionary` > `Save Dictionary`: Saves the current dictionary data back to the loaded dictionary file. Enabled only if a dictionary file is loaded.
    *   `Dictionary` > `Save Dictionary As...`: Saves the current dictionary data to a new or different JSON file.
10. **Set Target Language:** Use `Language` > `Set Target Language...` to input the name of the language you are translating into (displayed in the status bar).
11. **Exit:** `File` > `Exit` (Alt+F4) or close the window. You will be prompted to save if there are unsaved changes.

## File Formats

*   **FTL File (`.ftl`):** The application expects basic Fluent Translation List files. It primarily handles lines in the format `key = value`, comments starting with `#`, section markers (`##`, `--`), and blank lines. It *does not* process more complex Fluent syntax like selectors, variables, or functions. Files should ideally be UTF-8 encoded.
*   **Dictionary File (`.json`):** A simple JSON file containing key-value pairs, where the key is the source language string and the value is the target language string. Example:
    ```json
    {
        "Hello World": "Bonjour le monde",
        "File": "Fichier",
        "Save": "Enregistrer"
    }
    ```
    Files should be UTF-8 encoded.

## Limitations

*   **Simple FTL Parsing:** Only parses basic `key = value` lines, comments, sections, and blanks. Complex Fluent syntax (selectors, attributes, variables, functions) is not supported yet and might be treated as comments or cause errors.
*   **Basic Error Checking:** Only checks for missing translations and mismatched ending punctuation. It doesn't validate placeholders, HTML tags, or other potential translation issues.
*   **Encoding:** Assumes files are UTF-8 encoded. Errors may occur with other encodings.

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs or feature suggestions.
