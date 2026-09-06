import java.io.FileInputStream
import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.google.gms.google-services")
}

// Enrollment config lives in local.properties (git-ignored, per-machine).
// Keys: mcpNotif.enrollUrl, mcpNotif.enrollToken
val localProps = Properties().apply {
    val f = rootProject.file("local.properties")
    if (f.exists()) load(FileInputStream(f))
}
val enrollUrl = localProps.getProperty("mcpNotif.enrollUrl")
    ?: throw GradleException("Missing 'mcpNotif.enrollUrl' in android-app/local.properties")
if (!enrollUrl.startsWith("https://")) {
    throw GradleException("mcpNotif.enrollUrl must be an https:// URL (got: $enrollUrl); the ENROLLMENT_TOKEN must not be sent over plaintext.")
}
val enrollToken = localProps.getProperty("mcpNotif.enrollToken")
    ?: throw GradleException("Missing 'mcpNotif.enrollToken' in android-app/local.properties")

android {
    namespace = "com.jgn.mcpnotif"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.jgn.mcpnotif"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "1.0"

        buildConfigField("String", "ENROLL_URL", "\"${enrollUrl}\"")
        buildConfigField("String", "ENROLL_TOKEN", "\"${enrollToken}\"")
    }

    buildFeatures {
        buildConfig = true
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation(platform("com.google.firebase:firebase-bom:33.5.1"))
    implementation("com.google.firebase:firebase-messaging")

    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("com.google.android.material:material:1.12.0")
    implementation("androidx.constraintlayout:constraintlayout:2.1.4")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.6")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")
}
