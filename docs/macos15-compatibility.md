# macOS 15.6 / M1 compatibility build

This is a custom source adaptation of upstream Compositor 1.4.5, based on commit
`11d8d7a50992b24fd9a760a1c13b1c01b70aaf30`. It is intended for an Apple-silicon
Mac running macOS 15.6 or later, including the M1 MacBook Air with 8 GB RAM.
It is not an official upstream release.

**Validation status:** built and smoke-tested locally on macOS 15.6 ARM64 with
Command Line Tools Swift 6.1.2 and the macOS 15.5 SDK. ARM64, minimum OS, ad-hoc
signature, sandbox entitlements, DMG verification and mounting passed. The app
launched from the mounted DMG; PNG import, painting, undo/redo, save/reopen and
PNG export with decoded pixel checks passed. See `runtime-validation.txt` for
exact scope and results. Full Xcode is not installed, so its test target was not
run; large-project performance and advanced tools were not comprehensively tested.

## Changes

- Set the project and unit-test deployment targets to macOS 15.6; retain ARM64.
- Guard macOS 26's `ToolbarSpacer` and `sharedBackgroundVisibility`. Sequoia uses
  the same tab strip and zoom controls with older toolbar spacing.
- Use the standard rounded AppKit pop-up bezel on Sequoia instead of the
  macOS 26-only `borderShape` property. Tahoe keeps the capsule appearance.
- Remove Sparkle, its update menu, package dependency, feed configuration, and
  helper-service entitlements. This build cannot automatically replace itself
  with an upstream macOS 26-only build. Update it manually from reviewed source.
- Use `com.wonderassembly.compositor.macos15` as the app identifier, separate
  from upstream. Existing app preferences, recent-file history, sandbox grants,
  and saved window state are not automatically migrated. Project files retain
  their existing format and can be opened explicitly.
- Scale the two disposable CPU raster-cache budgets with physical memory. Each
  is capped at 256 MiB of derived RGBA pixels on an 8 GiB Mac, rather than the
  previous 800 MB / 600 MB ceilings. These are soft cache budgets, not a cap on
  total application memory. The currently used entry and its source images can
  exceed them. Large images, effects, masks, GPU buffers and multiple open tabs
  still need substantial memory. No image-resolution or document-format limit
  was lowered, and all editing features are retained.

## Build with the installed Command Line Tools

This adaptation includes a direct clang + swiftc build for this Mac's existing
CLT 16.4 / Swift 6.1.2 and SDK 15.5. Full Xcode is unnecessary for this route.
The system's default SDK is 26.2, which cannot be imported by this Swift compiler;
the script explicitly selects `/Library/Developer/CommandLineTools/SDKs/MacOSX15.5.sdk`.
No toolchain installation or system developer-directory change is performed.

```sh
bash scripts/build-macos15-dmg.sh
```

`COMPOSITOR_DIST` can select a different output directory, and `COMPOSITOR_SDK`
can select an already installed, compiler-compatible SDK. The supplied defaults
are the ones tested on this Mac. The script:

1. Compiles the nine pixel-work C sources with clang `-O3`.
2. Compiles all Swift sources with `-O`, whole-module optimization and one backend
   thread. Module caches and objects stay in the project's `build-clt/` directory
   for diagnostics and retries. It checks for at least 1.5 GiB of free disk before
   compilation and packaging; this is a guard, not a guarantee of maximum use.
3. Constructs the app bundle and generates its ICNS from the existing PNG icons
   using `iconutil`. The only asset resources are the app icon and the standard
   system accent color; Metal kernels are compiled from source at runtime.
4. Signs ad hoc with hardened runtime and the existing sandbox and user-selected
   file entitlements. Checks ARM64, minimum OS 15.6, bundle identifier, absence
   of Sparkle, signature and entitlements.
5. Creates and verifies a compressed DMG with an Applications shortcut using
   `hdiutil`. The runnable app, DMG, build log and metadata are in `dist/`.

The script leaves its own build directory for review. It does not install the
app, publish files, contact a notarization service, or change security policy.
Timestamps and signatures mean outputs need not be byte-for-byte reproducible.
The app is **ad-hoc signed, not Developer ID signed or notarized**. Approve only
trusted downloaded builds through normal macOS Privacy & Security if blocked.

## Swift 6.1 isolation migration

Actual type checking and module emission on this CLT 16.4 toolchain accept the
existing type/extension `nonisolated` declarations. They have been retained,
as have method-level isolation declarations. Swift 6.1 has no project-wide
MainActor default equivalent to the original Swift 6.2 project setting, so the
mutable editor session, history, edit-state classes, AppKit coordinators and
GPU write state now carry explicit `@MainActor` annotations. Worker actors and
nonisolated rendering/data types retain their existing isolation.

The PSD reader's eight-byte big-endian expression has been split into an
explicit eight-step accumulation because the older compiler timed out on the
long overloaded expression. Metal is imported with `@preconcurrency` in the
Sendable pipeline wrapper because SDK 15.5 lacks the newer Metal Sendable
annotations. These are compiler compatibility changes; the project file
format remains version 11.

## Optional manual GitHub build

`.github/workflows/build-macos15.yml` is a manual `workflow_dispatch` build using
an installed Xcode 26.3 on a `macos-15` runner. It uploads artifacts for seven
days and does not create a release. It has not been run. If a future runner image
no longer includes Xcode 26.3, select another already-installed compatible Xcode.
Running it requires your explicit choice and can consume your GitHub Actions
allowance or incur charges according to your plan. A CI build alone does not
validate the app on your exact macOS 15.6 / 8 GB device.

## Verification on the target Mac

Build and run the existing unit suite with an appropriate installed Xcode:

```sh
xcodebuild test -project Compositor.xcodeproj -scheme Compositor \
  -destination 'platform=macOS,arch=arm64' -only-testing:CompositorTests \
  -parallel-testing-enabled NO -jobs 2 \
  CODE_SIGN_STYLE=Manual CODE_SIGN_IDENTITY=- DEVELOPMENT_TEAM=
```

Do not infer success from a partial or failed run. Some existing tests show
windows and are sensitive to OS UI behavior. `CompatibilityBudgetTests` covers
the new pure cache-budget calculation; it still needs execution on macOS.

Then launch the built app and check:

- A new canvas opens; toolbars fit the 13-inch display, including a narrow window.
- Several project tabs can be created, switched, scrolled and closed; tab/zoom
  controls remain reachable and each tab preserves its project.
- Blend-mode and font menus open, preview, commit and cancel normally.
- Import a JPEG/PNG and a modest layered PSD; edit, undo/redo, save a `.comp`,
  close and reopen it; export JPEG and inspect the pixels.
- Paint, erase, transform, layer masks and layer effects render correctly.
- Vision subject selection/removal, a RAW import and GPU effects work or report
  failures clearly; no unexpected crash or blank canvas appears.
- Watch Activity Monitor memory pressure with a modest real project. Avoid using
  maximum-size documents as an initial smoke test. Advanced background removal
  and many effects on a high-resolution image can still use multiple gigabytes.
- Launch through Finder from the packaged DMG copy, not just from Xcode; inspect
  the signature, minimum-OS metadata and DMG checksums produced by the script.

## Static checks performed in Linux

The final handoff reports exact results for `git diff --check`, shell syntax,
plist/scheme XML and workflow YAML parsing, and available portable C syntax
checks. These checks cannot validate SwiftUI type inference, AppKit availability,
Metal behavior, signing, DMG creation or actual macOS runtime compatibility.
