# Adding a language

1. Copy `_template.json` to `<language code>.json` (for example `fr.json`).
2. Fill in the `"translation"` value of each entry — the `"english"` value shows what it means
   and stays untouched.
3. Reload the page. Entries left empty simply fall back to English, so partial translations work.

Plain files like `en.json` (`"code": "text"`) work as well — both shapes are accepted.
The app only loads languages offered in its language dropdown (en, de, fr, ja).
