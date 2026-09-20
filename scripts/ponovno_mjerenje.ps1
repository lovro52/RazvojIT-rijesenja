# Ponovno mjerenje na kanonskom popisu datoteka.
# Regenerira baseline i LLaMA rezultate na ocuvanom ispitnom skupu.
# Sav ispis ide i na zaslon i u rezultati\ponovno_mjerenje.log

$ErrorActionPreference = 'Continue'
Set-Location 'C:\Projects\Diplomski'

$log = 'C:\Projects\Diplomski\rezultati\ponovno_mjerenje.log'
if (Test-Path $log) { Remove-Item $log }

$d = 'C:\Projects\Diplomski\data\uploads'
$f = @(
  "$d\20260310_200329_Tuesday-WorkingHours.pcap_ISCX.csv",
  "$d\20260330_124032_Tuesday-WorkingHours.pcap_ISCX.csv",
  "$d\20260402_110002_Wednesday-workingHours.pcap_ISCX.csv",
  "$d\20260819_160042_Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv",
  "$d\20260819_160602_Friday-WorkingHours-Afternoon-PortScan.pcap_ISCX.csv",
  "$d\20260819_160804_Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv",
  "$d\20260916_150528_test_flows.csv"
)

# virtualno okruzenje ako postoji
$venv = 'C:\Projects\Diplomski\.venv-1\Scripts\python.exe'
if (Test-Path $venv) { $py = $venv } else { $py = 'python' }

"=== POCETAK $(Get-Date -Format 'HH:mm:ss') ===" | Tee-Object -FilePath $log -Append
"python: $py" | Tee-Object -FilePath $log -Append

"`n=== 1. BASELINE (XGBoost, Random Forest) ===" | Tee-Object -FilePath $log -Append
& $py scripts\baseline_usporedba.py --csv $f 2>&1 | Tee-Object -FilePath $log -Append

"`n=== 2. LLAMA, OCISCENI SKUP ===" | Tee-Object -FilePath $log -Append
& $py scripts\evaluiraj_gguf.py --model llama32-netlograg-v3 --limit 600 --csv $f 2>&1 | Tee-Object -FilePath $log -Append

"`n=== GOTOVO $(Get-Date -Format 'HH:mm:ss') ===" | Tee-Object -FilePath $log -Append
