Invoke-AtomicRunner -listOfAtomics .\LabAtomic.csv -GetPrereqs
Start-Sleep -Seconds 5
Invoke-AtomicRunner -listOfAtomics .\LabAtomic.csv -PauseBetweenAtomics 5
Start-Sleep -Seconds 5
Invoke-AtomicRunner -listOfAtomics .\LabAtomic.csv -Cleanup

