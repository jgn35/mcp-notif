import java.io.FileInputStream
import java.util.Properties
import org.gradle.api.attributes.Attribute

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// google-services plugin requires google-services.json (git-ignored).
// Only apply it when the file is present (local builds). CI skips it.
if (rootProject.file("app/google-services.json").exists()) {
    apply(plugin = "com.google.gms.google-services")
}

val localProps = Properties().apply {
    val f = rootProject.file("local.properties")
    if (f.exists()) load(FileInputStream(f))
}

// In CI (no local.properties), use placeholder values so the build succeeds
// without real enrollment credentials. Real builds require local.properties.
val enrollUrl = localProps.getProperty("mcpNotif.enrollUrl")
    ?: "https://ci-placeholder.example.com"
val enrollToken = localProps.getProperty("mcpNotif.enrollToken")
    ?: "ci-placeholder-token"

if (rootProject.file("local.properties").exists()) {
    if (!enrollUrl.startsWith("https://")) {
        throw GradleException("mcpNotif.enrollUrl must be an https:// URL")
    }
}

android {
    namespace = "com.jgn.mcpnotif"
    // CI uses API 35 (widely available); local builds use 37 (installed on the dev machine).
    val sdkVersion = (System.getenv("CI_COMPILE_SDK") ?: "37").toInt()
    compileSdk = sdkVersion

    defaultConfig {
        applicationId = "com.jgn.mcpnotif"
        minSdk = 26
        targetSdk = sdkVersion
        versionCode = 1
        versionName = "1.0"
        buildConfigField("String", "ENROLL_URL", "\"${enrollUrl}\"")
        buildConfigField("String", "ENROLL_TOKEN", "\"${enrollToken}\"")
    }

    buildFeatures { buildConfig = true }

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
    kotlinOptions { jvmTarget = "17" }

    testOptions {
        unitTests { isIncludeAndroidResources = true }
    }
}

dependencies {
    implementation(platform("com.google.firebase:firebase-bom:34.18.0"))
    implementation("com.google.firebase:firebase-messaging")
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("com.google.android.material:material:1.12.0")
    implementation("androidx.constraintlayout:constraintlayout:2.1.4")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.6")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")

    testImplementation("junit:junit:4.13.2")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.8.1")
    testImplementation("androidx.test:core:1.6.1")
    testImplementation("androidx.test.ext:junit:1.2.1")
    testImplementation("org.json:json:20240303")
}

configurations.matching { it.name == "debugUnitTestCompileClasspath" }.configureEach {
    attributes.attribute(Attribute.of("artifactType", String::class.java), "jar")
}
