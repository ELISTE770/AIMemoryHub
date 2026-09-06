from pathlib import Path

def main():
    p = Path('web/index.html')
    # Copy from public/index.html if exists or write our modern template
    print('Ready to write web/index.html')

if __name__ == '__main__':
    main()
