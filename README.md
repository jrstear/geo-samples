# geo-samples

Example outputs and sample data for the
[geo](https://github.com/jrstear/geo) drone-photogrammetry pipeline and the
[odium](https://github.com/jrstear/odium) Claude-Agent-SDK orchestrator.

## Examples

- **[odm-ortho-error/](odm-ortho-error/)** —
  root-cause investigation of a long-standing ODM orthophoto accuracy bug,
  end-to-end validation of the two open upstream fixes
  ([OpenSfM#48](https://github.com/OpenDroneMap/OpenSfM/pull/48) and
  [ODM#2008](https://github.com/OpenDroneMap/ODM/pull/2008)) on a 1385-image
  drone survey, and the full `rmse.html` reports for the baseline and patched
  runs. Patched ODM exceeds Pix4D on the same dataset (CHK RMS_H 0.28 ft vs
  0.72 ft).

## Future

- Sample ODM datasets for trying the pipeline end-to-end
- Example QGIS project files
- Tutorial walkthroughs
