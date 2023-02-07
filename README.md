# Minecraft Launcher

A simple Minecraft Launcher written in Python. (Developed in Python 3.11.1 64-bit)

Usage:
```bash
python minecraft.py [OPTIONS]
```

Available options:
```text
--list
    List all available Minecraft versions.

--version=<version>
    Specify Minecraft version, e.g., 1.8, 1.13, and 1.19.3.
    This option is ignored if "--mod" option is set.

--mod=<manifest filepath>
    Launch Minecraft with specific mod loader, e.g., ".minecraft/versions/fabric-loader-0.14.13-1.19.3/fabric-loader-0.14.13-1.19.3.json".

--classpath=<classpath>
    Extends the classpath of the JVM. As this string value is added to the classpath directly, make sure to use the correct seperator.

--gameDir=<directory>
    Specify the Minecraft game directory. Defaults to the .minecraft directory.

--ms-login
    Login with a Microsoft account.
    Warning: This options uses STDIN to prompt if no refresh token is found.

--token=<token filepath>
    Scecify the refresh token file.
    This option is ignored if "--ms-login" option is not set.

--mojang-login
    Login with a Mojang account.
    Warning: This options uses STDIN to prompt.

--no-launch
    Do not launch Minecraft. Download manifests, libraries, and assets only.
```