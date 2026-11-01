# Preserved source issues

- The nested file `Tomahawk_Rev22_RMAPLA_PoC_Results.zip` inside
  `Tomahawk_Rev22_RMAPLA_Kaggle_PoC_Upload.zip` raises `BadZipFile` when opened.
  It begins with a ZIP local header and is 950,272 bytes long, but could not be read
  as a complete archive. The enclosing original is retained unchanged; no silent
  repair or replacement is represented as an original result.
- The credential-pattern scan found no matches in the text it could inspect. The
  unreadable nested ZIP is a recorded scan limit, not a successful scan of its contents.
- Some notebooks are unexecuted or contain error outputs. The execution index records
  those facts. All are retained, as requested, alongside successful runs.
