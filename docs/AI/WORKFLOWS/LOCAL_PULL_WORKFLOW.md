# Local Pull Workflow

After Kiro pushes:

```powershell
cd "D:\SaaSprojectService\Rasti chekFinal 10 tir"
git status
```

If clean:

```powershell
git pull
python manage.py check
python manage.py test <related_tests>
python manage.py runserver
```

If not clean:

Send output of:

```powershell
git status --short
```

to ChatGPT before pulling.
