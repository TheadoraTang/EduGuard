# Data Directory

- `raw/`: local raw datasets such as StudyChat or MathDial downloads. This directory is ignored by Git.
- `processed/`: generated intermediate files, predictions, review samples, and evaluation outputs. This directory is ignored by Git.
- `demo/`: sanitized demo data that can be committed with the application.
- `uploads/`: local user-uploaded files created by the running backend. This directory is ignored by Git.
- `models/`: optional local ML classifier artifacts. Large model files should be reviewed before committing.

StudyChat is distributed under CC BY 4.0. Cite the StudyChat dataset and paper by McNichols, Ikram, and Lan when using it in reports or papers. EduGuard uses such datasets for behavior-label research, manual evaluation, and anonymized aggregate analysis; raw conversations should not be committed or treated as direct evidence of real student risk without human review.
