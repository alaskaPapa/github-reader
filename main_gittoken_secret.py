from fastapi import FastAPI, HTTPException, Request, Depends
from pydantic import BaseModel
import os
import shutil
import asyncio
from git import Repo

app = FastAPI()

# 从环境变量中读取 GitHub Token 和访问密码
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
ACCESS_PASSWORD = os.getenv("ACCESS_PASSWORD")

class GitRepo(BaseModel):
    git_url: str

# 依赖项，用于验证密码
async def verify_password(request: Request):
    if "Authorization" not in request.headers:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    if request.headers["Authorization"] != ACCESS_PASSWORD:
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.get("/", dependencies=[Depends(verify_password)])
async def get_main():
    return {"message": "Welcome to Code Reader!"}

@app.post("/get-repo-content/", dependencies=[Depends(verify_password)])
async def print_repo_url(repo: GitRepo):
    git_url = repo.git_url
    try:
        repo_name = git_url.split("/")[-1]
        repo_name = (
            repo_name.replace(".git", "") if repo_name.endswith(".git") else repo_name
        )

        temp_dir = f"./temp_{repo_name}"
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        os.makedirs(temp_dir)

        repo_dir = os.path.join(temp_dir, repo_name)
        print("start cloning")
        # 异步克隆仓库
        await clone_repo_async(git_url, repo_dir)

        print("start reading")
        # 异步读取所有文件
        content = await read_all_files_async(repo_dir)
        print("read finished. content length: ", len(content))
        # 确保在此处删除临时目录
        shutil.rmtree(temp_dir)
        print("temp dir removed")
        return {"content": content[:50000]}

    except Exception as e:
        # 如果出现异常，也应该清理临时目录
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        raise HTTPException(status_code=500, detail=str(e))

async def clone_repo_async(git_url, repo_dir):
    loop = asyncio.get_event_loop()
    print(f"开始克隆仓库: {git_url}")
    await loop.run_in_executor(
        None, 
        lambda: Repo.clone_from(
            git_url, 
            repo_dir, 
            depth=1, 
            env={"GIT_ASKPASS": os.path.abspath('askpass.py')}, 
            config={"http.extraHeader": f"Authorization: token {GITHUB_TOKEN}"}
        )
    )
    print(f"仓库克隆完成: {repo_dir}")

async def read_all_files_async(directory):
    loop = asyncio.get_event_loop()
    print(f"开始读取文件: {directory}")
    content = await loop.run_in_executor(None, lambda: read_all_files(directory))
    print(f"文件读取完成. 总字符数: {len(content)}")
    return content

def read_all_files(directory):
    all_text = ""
    for root, dirs, files in os.walk(directory):
        for file_name in files:
            file_path = os.path.join(root, file_name)
            if os.path.isfile(file_path):
                try:
                    with open(file_path, "r", encoding="utf-8") as file:
                        all_text += f"File: {file_name}\n\n" + file.read() + "\n\n"
                except UnicodeDecodeError:
                    print(f"无法以UTF-8编码读取文件: {file_path}")
                except Exception as e:
                    print(f"读取文件时发生错误: {file_path}, 错误: {e}")
    return all_text

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080)
