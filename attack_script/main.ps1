$numFile = 8

for ($i = 6; $i -le $numFile; $i++) {
    $file = ".\scenario_$i.csv"
    
    if (Test-Path $file) {
        Invoke-AtomicRunner -listOfAtomics $file -GetPrereqs
        Start-Sleep -Seconds 10
        
        Invoke-AtomicRunner -listOfAtomics $file -PauseBetweenAtomics 20
        Start-Sleep -Seconds 10

        Invoke-AtomicRunner -listOfAtomics $file -Cleanup
    } else {
        Write-Warning "File not found."
    }
}