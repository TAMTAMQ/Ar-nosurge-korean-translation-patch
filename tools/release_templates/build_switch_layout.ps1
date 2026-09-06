param(
    [ValidateSet('Atmosphere', 'Ryujinx')][string]$Target,
    [Nullable[bool]]$WithFps,
    [switch]$NoOpen,
    [switch]$Quiet
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

function Select-Target {
    $form = New-Object System.Windows.Forms.Form
    $form.Text = '아르노사쥬 DX 한국어 패치'
    $form.Size = New-Object System.Drawing.Size(410, 175)
    $form.StartPosition = 'CenterScreen'
    $form.FormBorderStyle = 'FixedDialog'
    $form.MaximizeBox = $false
    $form.MinimizeBox = $false

    $label = New-Object System.Windows.Forms.Label
    $label.Text = '사용할 환경을 선택하세요.'
    $label.AutoSize = $true
    $label.Location = New-Object System.Drawing.Point(125, 25)
    $form.Controls.Add($label)

    $atmosphere = New-Object System.Windows.Forms.Button
    $atmosphere.Text = 'Atmosphere'
    $atmosphere.Size = New-Object System.Drawing.Size(145, 45)
    $atmosphere.Location = New-Object System.Drawing.Point(42, 65)
    $atmosphere.DialogResult = [System.Windows.Forms.DialogResult]::Yes
    $form.Controls.Add($atmosphere)

    $ryujinx = New-Object System.Windows.Forms.Button
    $ryujinx.Text = 'Ryujinx'
    $ryujinx.Size = New-Object System.Drawing.Size(145, 45)
    $ryujinx.Location = New-Object System.Drawing.Point(207, 65)
    $ryujinx.DialogResult = [System.Windows.Forms.DialogResult]::No
    $form.Controls.Add($ryujinx)

    $result = $form.ShowDialog()
    $form.Dispose()
    if ($result -eq [System.Windows.Forms.DialogResult]::Yes) { return 'Atmosphere' }
    if ($result -eq [System.Windows.Forms.DialogResult]::No) { return 'Ryujinx' }
    throw '환경 선택을 취소했습니다.'
}

if (-not $Target) { $Target = Select-Target }
$payload = Join-Path $PSScriptRoot 'payload'
$romfsSource = Join-Path $payload 'romfs'
$uiPatch = Join-Path $payload 'exefs\ArNosurgeKoreanUI\28F3C3965CEB60AC18A23E2B2C0C4BEEE3C81D8B.ips'
$fpsPatch = Join-Path $payload 'exefs\ArNosurgeFpsUnlock\28F3C3965CEB60AC18A23E2B2C0C4BEEE3C81D8B.ips'
if (-not (Test-Path -LiteralPath $romfsSource)) { throw 'payload\romfs 폴더가 없습니다.' }

$includeFps = $false
if ($null -ne $WithFps) {
    $includeFps = [bool]$WithFps
} elseif (Test-Path -LiteralPath $fpsPatch) {
    $fpsAnswer = [System.Windows.Forms.MessageBox]::Show(
        '선택형 60FPS 프레임 제한 해제 패치도 포함할까요?',
        '60FPS 패치 선택',
        [System.Windows.Forms.MessageBoxButtons]::YesNoCancel,
        [System.Windows.Forms.MessageBoxIcon]::Question
    )
    if ($fpsAnswer -eq [System.Windows.Forms.DialogResult]::Cancel) { throw '작업을 취소했습니다.' }
    $includeFps = $fpsAnswer -eq [System.Windows.Forms.DialogResult]::Yes
}

$output = Join-Path $PSScriptRoot 'output'
if (Test-Path -LiteralPath $output) { Remove-Item -LiteralPath $output -Recurse -Force }

if ($Target -eq 'Atmosphere') {
    $romfsDestination = Join-Path $output 'atmosphere\contents\01003CF0128DE000\romfs'
    New-Item -ItemType Directory -Path $romfsDestination -Force | Out-Null
    Copy-Item -Path (Join-Path $romfsSource '*') -Destination $romfsDestination -Recurse -Force
    if (Test-Path -LiteralPath $uiPatch) {
        $uiDestination = Join-Path $output 'atmosphere\exefs_patches\ArNosurgeKoreanUI'
        New-Item -ItemType Directory -Path $uiDestination -Force | Out-Null
        Copy-Item -LiteralPath $uiPatch -Destination $uiDestination -Force
    }
    if ($includeFps -and (Test-Path -LiteralPath $fpsPatch)) {
        $fpsDestination = Join-Path $output 'atmosphere\exefs_patches\ArNosurgeFpsUnlock'
        New-Item -ItemType Directory -Path $fpsDestination -Force | Out-Null
        Copy-Item -LiteralPath $fpsPatch -Destination $fpsDestination -Force
    }
} else {
    $base = Join-Path $output 'mods\contents\01003cf0128de000'
    $romfsDestination = Join-Path $base 'korean_final\romfs'
    New-Item -ItemType Directory -Path $romfsDestination -Force | Out-Null
    Copy-Item -Path (Join-Path $romfsSource '*') -Destination $romfsDestination -Recurse -Force
    if (Test-Path -LiteralPath $uiPatch) {
        $uiDestination = Join-Path $base 'korean_final\exefs'
        New-Item -ItemType Directory -Path $uiDestination -Force | Out-Null
        Copy-Item -LiteralPath $uiPatch -Destination $uiDestination -Force
    }
    if ($includeFps -and (Test-Path -LiteralPath $fpsPatch)) {
        $fpsDestination = Join-Path $base 'fps_unlock\exefs'
        New-Item -ItemType Directory -Path $fpsDestination -Force | Out-Null
        Copy-Item -LiteralPath $fpsPatch -Destination $fpsDestination -Force
    }
}

if (-not $Quiet) {
    [System.Windows.Forms.MessageBox]::Show(
        "${Target}용 패치 폴더를 만들었습니다.`n$output",
        '완료',
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Information
    ) | Out-Null
}
if (-not $NoOpen) { Start-Process explorer.exe -ArgumentList $output }
