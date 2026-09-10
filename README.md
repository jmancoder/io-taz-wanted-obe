# Taz: Wanted OBE Importer
A Blender add-on for extracting .pc archives from Taz: Wanted, then importing .obe models and .bmp textures from them. Blender 4.2+ is supported.
NOTE: The add-on is currently only designed for the PC version, and has only been tested on the Europe release.

## Installation
1. Download the latest version of this add-on from the [releases](https://github.com/jmancoder/io-taz-wanted-obe/releases) page.
2. In Blender, open _Edit->Preferences->Add-ons_.
3. Expand the dropdown arrow on the top right, click _Install from Disk_, and select the .zip file.

## Usage
### Extracting the PC Archives
1. Press N to expand the sidebar and open the _Taz: Wanted_ tab.
2. Click the folder icon to the right of _Output Folder_ and select an empty directory.
3. Click _Extract PC Archives_ and select one or more .pc files from the Paks folder of your game installation.
4. Click _Extract PC_ and wait for the operation to complete.
### Importing Assets
1. Click the folder icon to the right of _Manifest Path_, then navigate to the folder you extracted the PC archives to earlier.
2. Select the manifest.json file from the package you want to import from and click _Accept_.
2. Click _Import OBE_ in the sidebar, select the desired object file from the same package as the manifest, and click _Import OBE_. Textures will load automatically.

## TODO
- Fix flipped UVs on certain meshes
- Import async mesh nodes
- Import animations tracks
- Import game-specific GIF files
- Import more texture formats
- Test on more releases of Taz: Wanted
- Add support for the Xbox version

## Acknowledgements
[MilkGames](https://github.com/MilkGames/) - Provided decompiled source code for Taz: Wanted and its game engine