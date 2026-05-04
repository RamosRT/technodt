# Android TSD Setup

## Device

Connected device verified through ADB:

```text
3de6bc11    device
```

## Local SDK

Android SDK path on this workstation:

```text
C:\Users\Ramos\AppData\Local\Android\Sdk
```

ADB is available at:

```text
C:\Users\Ramos\AppData\Local\Android\Sdk\platform-tools\adb.exe
```

## Build

The Android project lives in:

```text
E:\technodt\android
```

Build command:

```powershell
cd E:\technodt\android
.\gradlew.bat :app:assembleDebug
```

Install debug APK:

```powershell
C:\Users\Ramos\AppData\Local\Android\Sdk\platform-tools\adb.exe install -r app\build\outputs\apk\debug\app-debug.apk
```

