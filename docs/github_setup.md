# Adding the NeoPixel files to your own repository

This guide explains how to copy the four NeoPixel related files that ship with this repository into your own project and publish them on GitHub.

## 1. Make sure your repository is up to date

If you already cloned your personal repository, update it to the latest state before copying new files:

```bash
git pull
```

If you have not cloned it yet, do so now:

```bash
git clone <YOUR-REPO-URL>
cd <YOUR-REPO-NAME>
```

## 2. Copy the files into your repository

From the directory that contains your clone of this project (`wyoming-satellite`), copy the following files into the same relative locations inside your repository:

| Source file in this repository | Destination path in your repository |
| ------------------------------ | ----------------------------------- |
| `wyoming_satellite/neopixel_ring.py` | `wyoming_satellite/neopixel_ring.py` |
| `examples/neopixel_service.py` | `examples/neopixel_service.py` |
| `docs/neopixel_service.md` | `docs/neopixel_service.md` |
| `README.md` (only the NeoPixel section) | Merge the "NeoPixel LED feedback" section into your README |

You can use `cp --parents` to preserve the folder structure when copying:

```bash
cp --parents wyoming_satellite/neopixel_ring.py \
  examples/neopixel_service.py \
  docs/neopixel_service.md \
  README.md \
  /path/to/your/repository
```

Alternatively, copy the files manually with your text editor or file manager.

> **Tip:** If your repository does not already have `docs/`, `examples/`, or `wyoming_satellite/` directories, create them before copying:
>
> ```bash
> mkdir -p docs examples wyoming_satellite
> ```

## 3. Review the changes

Inside your repository, list the pending modifications:

```bash
git status
```

Open the files to make sure the copied content looks correct. Adjust paths, imports, or configuration values if your project structure differs.

## 4. Stage the files

Use `git add` to stage the new or updated files:

```bash
git add wyoming_satellite/neopixel_ring.py \
        examples/neopixel_service.py \
        docs/neopixel_service.md \
        README.md
```

If you intentionally only copied part of `README.md`, stage just that file after editing it in your repository.

## 5. Commit your changes

Create a descriptive commit message:

```bash
git commit -m "Add NeoPixel service files"
```

## 6. Push to GitHub

Send the commit to your remote repository:

```bash
git push
```

After the push succeeds, the files will be available on GitHub. If you are working on a branch, open a pull request so you can review and merge the changes into your main branch.

## 7. (Optional) Tag a release

If these changes represent a new version you want to share, create and push a tag:

```bash
git tag vX.Y.Z
git push origin vX.Y.Z
```

Replace `vX.Y.Z` with the version number you want to publish.

---

If anything goes wrong or Git reports conflicts, refer to the [GitHub Docs on resolving merge conflicts](https://docs.github.com/en/get-started/using-git/resolving-merge-conflicts) or ask for help with the specific error message you see.
