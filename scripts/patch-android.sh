#!/bin/bash
# Patch Android MainActivity — enable persistent WebView storage + cache
set -e

MAIN_ACTIVITY="android/app/src/main/java/com/machinehub/app/MainActivity.java"

if [ ! -f "$MAIN_ACTIVITY" ]; then
  echo "⚠ MainActivity not found: $MAIN_ACTIVITY"
  exit 0
fi

cat > "$MAIN_ACTIVITY" <<'JAVAEOF'
package com.machinehub.app;

import android.os.Bundle;
import android.webkit.WebSettings;
import android.webkit.WebView;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        try {
            WebView webView = this.bridge.getWebView();
            if (webView != null) {
                WebSettings settings = webView.getSettings();

                // Enable persistent storage (Service Worker + IndexedDB)
                settings.setDomStorageEnabled(true);
                settings.setDatabaseEnabled(true);
                settings.setAllowFileAccess(true);
                settings.setAllowContentAccess(true);
                settings.setCacheMode(WebSettings.LOAD_DEFAULT);
                settings.setJavaScriptEnabled(true);
                settings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);

                // Persistent storage path (already default on modern Android)
                // but we enforce it here for clarity
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}
JAVAEOF

echo "✓ MainActivity patched: $MAIN_ACTIVITY"
