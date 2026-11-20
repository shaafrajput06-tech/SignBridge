# SignBridge, shared copy: a tiny web server for this folder, using only Windows PowerShell (no Python or
# Node needed). It listens on this computer only (http://localhost), where browsers allow the camera, and
# opens the app in the default browser. Close this window to stop SignBridge.
param([int]$Port = 8765, [switch]$NoBrowser)

$ErrorActionPreference = "Stop"
$root = Join-Path $PSScriptRoot "site"
if (-not (Test-Path (Join-Path $root "index.html"))) { Write-Host "The 'site' folder is missing. Unzip the whole SignBridge zip first, then run Start SignBridge.bat again."; Read-Host "Press Enter to close"; exit 1 }

$types = @{
  ".html" = "text/html; charset=utf-8"; ".js" = "text/javascript; charset=utf-8"; ".mjs" = "text/javascript; charset=utf-8"
  ".css" = "text/css; charset=utf-8"; ".json" = "application/json; charset=utf-8"; ".wasm" = "application/wasm"
  ".mp4" = "video/mp4"; ".svg" = "image/svg+xml"; ".png" = "image/png"; ".ico" = "image/x-icon"
  ".task" = "application/octet-stream"; ".tflite" = "application/octet-stream"; ".txt" = "text/plain; charset=utf-8"
}

$listener = New-Object System.Net.HttpListener
$chosen = $null
foreach ($candidate in $Port..($Port + 10)) {
  try { $listener.Prefixes.Clear(); $listener.Prefixes.Add("http://localhost:$candidate/"); $listener.Start(); $chosen = $candidate; break } catch { $listener = New-Object System.Net.HttpListener }
}
if (-not $chosen) { Write-Host "Could not open a local port ($Port to $($Port + 10)). Close other programs and try again."; Read-Host "Press Enter to close"; exit 1 }

$url = "http://localhost:$chosen/"
Write-Host ""
Write-Host "  SignBridge is running at $url"
Write-Host "  Keep this window open while you use it. Close it to stop SignBridge."
Write-Host ""
if (-not $NoBrowser) { Start-Process $url }

$rootFull = [IO.Path]::GetFullPath($root)
while ($listener.IsListening) {
  try { $context = $listener.GetContext() } catch { break }
  $response = $context.Response
  try {
    $relative = [Uri]::UnescapeDataString($context.Request.Url.AbsolutePath.TrimStart("/"))
    if ($relative -eq "") { $relative = "index.html" }
    $path = [IO.Path]::GetFullPath((Join-Path $rootFull $relative))
    # Serve only files inside the site folder. The app has no server API here: it uses the browser instead.
    if (-not $path.StartsWith($rootFull.TrimEnd("\") + "\", [StringComparison]::OrdinalIgnoreCase) -or -not (Test-Path $path -PathType Leaf)) {
      $response.StatusCode = 404
    } else {
      $bytes = [IO.File]::ReadAllBytes($path)
      $extension = [IO.Path]::GetExtension($path).ToLowerInvariant()
      $response.ContentType = $(if ($types.ContainsKey($extension)) { $types[$extension] } else { "application/octet-stream" })
      $response.Headers.Add("Cache-Control", "no-cache")
      $response.ContentLength64 = $bytes.Length
      $response.OutputStream.Write($bytes, 0, $bytes.Length)
    }
  } catch {
    try { $response.StatusCode = 500 } catch {}
  } finally {
    try { $response.OutputStream.Close() } catch {}
  }
}
