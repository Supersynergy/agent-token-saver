# Repository artwork

`cover-awesome.png` is the existing upstream cover from commit ad5d0fa. It is
retained as upstream artwork so that presentation work survives the release.
No claim about Bun support or measured savings is encoded in that cover.

`social-preview.png` is a new 1280×640 deterministic release card. It was rendered
with librsvg from the repo-release-excellence card template, using the project
name, the Bun install command and version 5.1. The asset is under 1 MB. It contains
no downloaded photos, external logos or bundled font files. Project artwork is
covered by the repository MIT license.

The card is used by the compact README and ships with the release. GitHub's custom social preview
is a separate web setting; a committed image does not prove that setting changed.

For a future release, change the version and command text before rendering the
card again, then check both the pixel dimensions and the output size rather
than resizing the README cover by assumption. Keep the original cover intact.

The release card was saved as GitHub's custom social preview on November 12,
2026. The repository API confirmed `usesCustomOpenGraphImage: true` and returned
a repository-images URL after the upload. No browser profile debugging permission
was added; the upload used the native file chooser in the existing signed-in session.
