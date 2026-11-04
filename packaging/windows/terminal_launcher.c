/* Console bootstrap: unpack the public wheel payload and open the terminal UI. */
#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif
#include <windows.h>
#include <stdio.h>
#include <wchar.h>

static int write_resource(const wchar_t *path, int id) {
    HRSRC resource = FindResourceW(NULL, MAKEINTRESOURCEW(id), RT_RCDATA);
    if (!resource) return 0;
    DWORD size = SizeofResource(NULL, resource);
    const void *bytes = LockResource(LoadResource(NULL, resource));
    if (!bytes || !size) return 0;
    HANDLE file = CreateFileW(path, GENERIC_WRITE, 0, NULL, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) return 0;
    DWORD written = 0;
    BOOL ok = WriteFile(file, bytes, size, &written, NULL);
    CloseHandle(file);
    return ok && written == size;
}

int wmain(int argc, wchar_t **argv) {
    if (argc > 1 && wcscmp(argv[1], L"--version") == 0) {
        puts("voxd terminal installer 0.1.0");
        return 0;
    }
    wchar_t temp[MAX_PATH], root[MAX_PATH], archive[MAX_PATH], script[MAX_PATH];
    wchar_t system[MAX_PATH], executable[MAX_PATH], command[4096];
    DWORD length = GetTempPathW(MAX_PATH, temp);
    if (!length || length >= MAX_PATH - 64 || !GetTempFileNameW(temp, L"vxd", 0, root)) return 1;
    if (!DeleteFileW(root) || !CreateDirectoryW(root, NULL)) return 1;
    if (swprintf(archive, MAX_PATH, L"%ls\\payload.zip", root) < 0 ||
        swprintf(script, MAX_PATH, L"%ls\\launch.ps1", root) < 0) return 1;
    if (!write_resource(archive, 101) || !write_resource(script, 102)) {
        fputs("Could not unpack installer. Check free space and retry.\n", stderr);
        return 1;
    }
    length = GetSystemDirectoryW(system, MAX_PATH);
    if (!length || length >= MAX_PATH - 64) return 1;
    if (swprintf(executable, MAX_PATH, L"%ls\\WindowsPowerShell\\v1.0\\powershell.exe", system) < 0) return 1;
    if (swprintf(command, 4096, L"\"%ls\" -NoProfile -ExecutionPolicy Bypass -File \"%ls\" -Archive \"%ls\" -Target \"%ls\\package\"", executable, script, archive, root) < 0) return 1;
    STARTUPINFOW startup = {0};
    PROCESS_INFORMATION process = {0};
    startup.cb = sizeof(startup);
    puts("voxd | Terminal installer\nPreparing Python and the keyboard interface...\n");
    fflush(stdout);
    if (!CreateProcessW(executable, command, NULL, NULL, FALSE, 0, NULL, NULL, &startup, &process)) {
        fprintf(stderr, "Could not start Windows PowerShell (error %lu).\n", (unsigned long)GetLastError());
        return 1;
    }
    WaitForSingleObject(process.hProcess, INFINITE);
    DWORD result = 1;
    GetExitCodeProcess(process.hProcess, &result);
    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
    DeleteFileW(archive);
    DeleteFileW(script);
    RemoveDirectoryW(root);
    return (int)result;
}
