
from __future__ import annotations

import argparse
import ctypes
import getpass
import hashlib
import io
import json
import multiprocessing as mp
import os
import shutil
import struct
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, List, Optional, Tuple, Union


# =====================================================================
# RUTAS Y EXTENSIONES
# =====================================================================
ROOT = Path(__file__).resolve().parent
INPUT_DIR = ROOT / "por_desbloquear"
OUTPUT_DIR = ROOT / "crakeados"
PASSWORDS_DIR = ROOT / "Contraseñas"
HISTORY_DIR = ROOT / "historial"
HISTORY_FILE = HISTORY_DIR / "historial.jsonl"

PDF_EXTENSIONS = {".pdf"}
EXCEL_EXTENSIONS = {".xls", ".xlsx", ".xlsm", ".xltx", ".xltm"}
SUPPORTED_EXTENSIONS = PDF_EXTENSIONS | EXCEL_EXTENSIONS


# =====================================================================
# ACELERADOR POR GPU (OPENCL NATIVO VÍA CTYPES)
# =====================================================================
class GPUAccelerator:
    """Motor de fuerza bruta ejecutado directamente sobre los núcleos de la GPU."""

    def __init__(self) -> None:
        self.available: bool = False
        self.device_name: str = "No detectada"
        self._cl = None
        self._ctx = None
        self._queue = None
        self._device = None
        self._kernel_sha256 = None
        self._kernel_md5 = None
        self._init_opencl()

    def _init_opencl(self) -> None:
        try:
            if sys.platform == "win32":
                cl = ctypes.windll.LoadLibrary("OpenCL.dll")
            elif sys.platform == "darwin":
                cl = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/OpenCL.framework/OpenCL")
            else:
                cl = None
                for candidate in ("libOpenCL.so.1", "libOpenCL.so"):
                    try:
                        cl = ctypes.cdll.LoadLibrary(candidate)
                        break
                    except Exception:
                        continue
                if cl is None:
                    return
        except Exception:
            return

        # Firmas de tipos OpenCL (64-bit seguro)
        cl.clGetPlatformIDs.argtypes = [ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_uint32)]
        cl.clGetDeviceIDs.argtypes = [ctypes.c_void_p, ctypes.c_uint64, ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_uint32)]
        cl.clGetDeviceInfo.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_size_t, ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t)]
        cl.clCreateContext.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int32)]
        cl.clCreateContext.restype = ctypes.c_void_p
        cl.clCreateCommandQueue.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint64, ctypes.POINTER(ctypes.c_int32)]
        cl.clCreateCommandQueue.restype = ctypes.c_void_p
        cl.clCreateBuffer.argtypes = [ctypes.c_void_p, ctypes.c_uint64, ctypes.c_size_t, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int32)]
        cl.clCreateBuffer.restype = ctypes.c_void_p
        cl.clReleaseMemObject.argtypes = [ctypes.c_void_p]
        cl.clReleaseMemObject.restype = ctypes.c_int32
        cl.clCreateProgramWithSource.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_char_p), ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_int32)]
        cl.clCreateProgramWithSource.restype = ctypes.c_void_p
        cl.clBuildProgram.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p), ctypes.c_char_p, ctypes.c_void_p, ctypes.c_void_p]
        cl.clBuildProgram.restype = ctypes.c_int32
        cl.clCreateKernel.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.POINTER(ctypes.c_int32)]
        cl.clCreateKernel.restype = ctypes.c_void_p
        cl.clSetKernelArg.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_size_t, ctypes.c_void_p]
        cl.clSetKernelArg.restype = ctypes.c_int32
        cl.clEnqueueNDRangeKernel.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t), ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p)]
        cl.clEnqueueNDRangeKernel.restype = ctypes.c_int32
        cl.clEnqueueReadBuffer.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_size_t, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p)]
        cl.clEnqueueReadBuffer.restype = ctypes.c_int32
        cl.clFinish.argtypes = [ctypes.c_void_p]
        cl.clFinish.restype = ctypes.c_int32

        # Detectar plataformas y dispositivos GPU
        num_p = ctypes.c_uint32()
        if cl.clGetPlatformIDs(0, None, ctypes.byref(num_p)) != 0 or num_p.value == 0:
            return
        platforms = (ctypes.c_void_p * num_p.value)()
        cl.clGetPlatformIDs(num_p.value, platforms, None)

        chosen_device = None
        devs = None
        num_d = ctypes.c_uint32()
        for p in platforms:
            if cl.clGetDeviceIDs(p, 0xFFFFFFFF, 0, None, ctypes.byref(num_d)) == 0 and num_d.value > 0:
                devs = (ctypes.c_void_p * num_d.value)()
                cl.clGetDeviceIDs(p, 0xFFFFFFFF, num_d.value, devs, None)
                for d in devs:
                    buf = (ctypes.c_char * 256)()
                    cl.clGetDeviceInfo(d, 0x102B, 256, buf, None)  # CL_DEVICE_NAME
                    name = buf.value.decode("utf-8", errors="replace")
                    if any(term in name.lower() for term in ["geforce", "rtx", "gtx", "radeon", "nvidia", "amd", "arc"]):
                        chosen_device = d
                        self.device_name = name.strip()
                        break
                if chosen_device:
                    break

        if not chosen_device and devs is not None and num_d.value > 0:
            chosen_device = devs[0]
            buf = (ctypes.c_char * 256)()
            cl.clGetDeviceInfo(chosen_device, 0x102B, 256, buf, None)
            self.device_name = buf.value.decode("utf-8", errors="replace").strip()

        if not chosen_device:
            return

        err = ctypes.c_int32()
        ctx = cl.clCreateContext(None, 1, (ctypes.c_void_p * 1)(chosen_device), None, None, ctypes.byref(err))
        if err.value != 0 or not ctx:
            return
        queue = cl.clCreateCommandQueue(ctx, chosen_device, 0, ctypes.byref(err))
        if err.value != 0 or not queue:
            return

        self._cl = cl
        self._ctx = ctx
        self._queue = queue
        self._device = chosen_device
        self._compile_kernels()
        self.available = True

    def _compile_kernels(self) -> None:
        cl = self._cl
        ctx = self._ctx
        dev = self._device
        err = ctypes.c_int32()

        # -------------------------------------------------------------
        # Kernel OpenCL C: SHA-256 ultra optimizado (PDF R=5 y Hashes)
        # -------------------------------------------------------------
        sha256_src = b"""
        #define ROTRIGHT(a,b) (((a) >> (b)) | ((a) << (32-(b))))
        #define CH(x,y,z) (((x) & (y)) ^ (~(x) & (z)))
        #define MAJ(x,y,z) (((x) & (y)) ^ ((x) & (z)) ^ ((y) & (z)))
        #define EP0(x) (ROTRIGHT(x,2) ^ ROTRIGHT(x,13) ^ ROTRIGHT(x,22))
        #define EP1(x) (ROTRIGHT(x,6) ^ ROTRIGHT(x,11) ^ ROTRIGHT(x,25))
        #define SIG0(x) (ROTRIGHT(x,7) ^ ROTRIGHT(x,18) ^ ((x) >> 3))
        #define SIG1(x) (ROTRIGHT(x,17) ^ ROTRIGHT(x,19) ^ ((x) >> 10))

        __constant uint K[64] = {
            0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
            0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
            0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
            0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
            0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
            0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
            0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
            0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
        };

        __kernel void test_sha256(
            __global const uchar* passwords,
            __global const uint* lengths,
            __global const uchar* salt,
            uint salt_len,
            __global const uint* target_hash,
            __global int* result_index,
            uint count
        ) {
            uint gid = get_global_id(0);
            if (gid >= count || *result_index != -1) return;

            uint pw_len = lengths[gid];
            uint total_len = pw_len + salt_len;

            uchar m[64];
            for (int i = 0; i < 64; i++) m[i] = 0;

            uint offset = gid * 64;
            for (uint i = 0; i < pw_len; i++) m[i] = passwords[offset + i];
            for (uint i = 0; i < salt_len; i++) m[pw_len + i] = salt[i];

            m[total_len] = 0x80;
            ulong bit_len = (ulong)total_len * 8;
            m[63] = (uchar)(bit_len & 0xFF);
            m[62] = (uchar)((bit_len >> 8) & 0xFF);
            m[61] = (uchar)((bit_len >> 16) & 0xFF);
            m[60] = (uchar)((bit_len >> 24) & 0xFF);

            uint w[64];
            for (int t = 0; t < 16; t++) {
                w[t] = ((uint)m[t*4] << 24) | ((uint)m[t*4+1] << 16) | ((uint)m[t*4+2] << 8) | ((uint)m[t*4+3]);
            }
            for (int t = 16; t < 64; t++) {
                w[t] = SIG1(w[t-2]) + w[t-7] + SIG0(w[t-15]) + w[t-16];
            }

            uint a = 0x6a09e667, b = 0xbb67ae85, c = 0x3c6ef372, d = 0xa54ff53a;
            uint e = 0x510e527f, f = 0x9b05688c, g = 0x1f83d9ab, h = 0x5be0cd19;

            for (int t = 0; t < 64; t++) {
                uint t1 = h + EP1(e) + CH(e,f,g) + K[t] + w[t];
                uint t2 = EP0(a) + MAJ(a,b,c);
                h = g; g = f; f = e; e = d + t1; d = c; c = b; b = a; a = t1 + t2;
            }

            if ((a + 0x6a09e667) == target_hash[0] &&
                (b + 0xbb67ae85) == target_hash[1] &&
                (c + 0x3c6ef372) == target_hash[2] &&
                (d + 0xa54ff53a) == target_hash[3] &&
                (e + 0x510e527f) == target_hash[4] &&
                (f + 0x9b05688c) == target_hash[5] &&
                (g + 0x1f83d9ab) == target_hash[6] &&
                (h + 0x5be0cd19) == target_hash[7]) {
                *result_index = gid;
            }
        }
        """
        p_src = ctypes.c_char_p(sha256_src)
        p_len = ctypes.c_size_t(len(sha256_src))
        prog = cl.clCreateProgramWithSource(ctx, 1, ctypes.byref(p_src), ctypes.byref(p_len), ctypes.byref(err))
        cl.clBuildProgram(prog, 1, (ctypes.c_void_p * 1)(dev), None, None, None)
        self._kernel_sha256 = cl.clCreateKernel(prog, b"test_sha256", ctypes.byref(err))

        # -------------------------------------------------------------
        # Kernel OpenCL C: MD5 ultra optimizado (PDF R=2/3/4 y Excel 97)
        # -------------------------------------------------------------
        md5_src = b"""
        #define F(x, y, z) (((x) & (y)) | ((~x) & (z)))
        #define G(x, y, z) (((x) & (z)) | ((y) & (~z)))
        #define H(x, y, z) ((x) ^ (y) ^ (z))
        #define I(x, y, z) ((y) ^ ((x) | (~z)))
        #define ROTLEFT(a,b) (((a) << (b)) | ((a) >> (32-(b))))

        #define FF(a, b, c, d, x, s, ac) { (a) += F ((b), (c), (d)) + (x) + (uint)(ac); (a) = ROTLEFT ((a), (s)); (a) += (b); }
        #define GG(a, b, c, d, x, s, ac) { (a) += G ((b), (c), (d)) + (x) + (uint)(ac); (a) = ROTLEFT ((a), (s)); (a) += (b); }
        #define HH(a, b, c, d, x, s, ac) { (a) += H ((b), (c), (d)) + (x) + (uint)(ac); (a) = ROTLEFT ((a), (s)); (a) += (b); }
        #define II(a, b, c, d, x, s, ac) { (a) += I ((b), (c), (d)) + (x) + (uint)(ac); (a) = ROTLEFT ((a), (s)); (a) += (b); }

        void md5_transform(uint state[4], const uint block[16]) {
            uint a = state[0], b = state[1], c = state[2], d = state[3];
            FF (a, b, c, d, block[ 0], 7,  0xd76aa478); FF (d, a, b, c, block[ 1], 12, 0xe8c7b756);
            FF (c, d, a, b, block[ 2], 17, 0x242070db); FF (b, c, d, a, block[ 3], 22, 0xc1bdceee);
            FF (a, b, c, d, block[ 4], 7,  0xf57c0faf); FF (d, a, b, c, block[ 5], 12, 0x4787c62a);
            FF (c, d, a, b, block[ 6], 17, 0xa8304613); FF (b, c, d, a, block[ 7], 22, 0xfd469501);
            FF (a, b, c, d, block[ 8], 7,  0x698098d8); FF (d, a, b, c, block[ 9], 12, 0x8b44f7af);
            FF (c, d, a, b, block[10], 17, 0xffff5bb1); FF (b, c, d, a, block[11], 22, 0x895cd7be);
            FF (a, b, c, d, block[12], 7,  0x6b901122); FF (d, a, b, c, block[13], 12, 0xfd987193);
            FF (c, d, a, b, block[14], 17, 0xa679438e); FF (b, c, d, a, block[15], 22, 0x49b40821);

            GG (a, b, c, d, block[ 1], 5,  0xf61e2562); GG (d, a, b, c, block[ 6], 9,  0xc040b340);
            GG (c, d, a, b, block[11], 14, 0x265e5a51); GG (b, c, d, a, block[ 0], 20, 0xe9b6c7aa);
            GG (a, b, c, d, block[ 5], 5,  0xd62f105d); GG (d, a, b, c, block[10], 9,  0x02441453);
            GG (c, d, a, b, block[15], 14, 0xd8a1e681); GG (b, c, d, a, block[ 4], 20, 0xe7d3fbc8);
            GG (a, b, c, d, block[ 9], 5,  0x21e1cde6); GG (d, a, b, c, block[14], 9,  0xc33707d6);
            GG (c, d, a, b, block[ 3], 14, 0xf4d50d87); GG (b, c, d, a, block[ 8], 20, 0x455a14ed);
            GG (a, b, c, d, block[13], 5,  0xa9e3e905); GG (d, a, b, c, block[ 2], 9,  0xfcefa3f8);
            GG (c, d, a, b, block[ 7], 14, 0x676f02d9); GG (b, c, d, a, block[12], 20, 0x8d2a4c8a);

            HH (a, b, c, d, block[ 5], 4,  0xfffa3942); HH (d, a, b, c, block[ 8], 11, 0x8771f681);
            HH (c, d, a, b, block[11], 16, 0x6d9d6122); HH (b, c, d, a, block[14], 23, 0xfde5380c);
            HH (a, b, c, d, block[ 1], 4,  0xa4beea44); HH (d, a, b, c, block[ 4], 11, 0x4bdecfa9);
            HH (c, d, a, b, block[ 7], 16, 0xf6bb4b60); HH (b, c, d, a, block[10], 23, 0xbebfbc70);
            HH (a, b, c, d, block[13], 4,  0x289b7ec6); HH (d, a, b, c, block[ 0], 11, 0xeaa127fa);
            HH (c, d, a, b, block[ 3], 16, 0xd4ef3085); HH (b, c, d, a, block[ 6], 23, 0x04881d05);
            HH (a, b, c, d, block[ 9], 4,  0xd9d4d039); HH (d, a, b, c, block[12], 11, 0xe6db99e5);
            HH (c, d, a, b, block[15], 16, 0x1fa27cf8); HH (b, c, d, a, block[ 2], 23, 0xc4ac5665);

            II (a, b, c, d, block[ 0], 6,  0xf4292244); II (d, a, b, c, block[ 7], 10, 0x432aff97);
            II (c, d, a, b, block[14], 15, 0xab9423a7); II (b, c, d, a, block[ 5], 21, 0xfc93a039);
            II (a, b, c, d, block[12], 6,  0x655b59c3); II (d, a, b, c, block[ 3], 10, 0x8f0ccc92);
            II (c, d, a, b, block[10], 15, 0xffeff47d); II (b, c, d, a, block[ 1], 21, 0x85845dd1);
            II (a, b, c, d, block[ 8], 6,  0x6fa87e4f); II (d, a, b, c, block[15], 10, 0xfe2ce6e0);
            II (c, d, a, b, block[ 6], 15, 0xa3014314); II (b, c, d, a, block[13], 21, 0x4e0811a1);
            II (a, b, c, d, block[ 4], 6,  0xf7537e82); II (d, a, b, c, block[11], 10, 0xbd3af235);
            II (c, d, a, b, block[ 2], 15, 0x2ad7d2bb); II (b, c, d, a, block[ 9], 21, 0xeb86d391);

            state[0] += a; state[1] += b; state[2] += c; state[3] += d;
        }

        __kernel void test_md5(
            __global const uchar* passwords,
            __global const uint* lengths,
            __global const uint* target_hash,
            __global int* result_index,
            uint count
        ) {
            uint gid = get_global_id(0);
            if (gid >= count || *result_index != -1) return;

            uint pw_len = lengths[gid];
            uchar m[64];
            for (int i = 0; i < 64; i++) m[i] = 0;
            uint offset = gid * 64;
            for (uint i = 0; i < pw_len; i++) m[i] = passwords[offset + i];

            m[pw_len] = 0x80;
            ulong bit_len = (ulong)pw_len * 8;
            m[56] = (uchar)(bit_len & 0xFF);
            m[57] = (uchar)((bit_len >> 8) & 0xFF);
            m[58] = (uchar)((bit_len >> 16) & 0xFF);
            m[59] = (uchar)((bit_len >> 24) & 0xFF);

            uint block[16];
            for (int i = 0; i < 16; i++) {
                block[i] = (uint)m[i*4] | ((uint)m[i*4+1] << 8) | ((uint)m[i*4+2] << 16) | ((uint)m[i*4+3] << 24);
            }

            uint state[4] = {0x67452301, 0xefcdab89, 0x98badcfe, 0x10325476};
            md5_transform(state, block);

            if (state[0] == target_hash[0] && state[1] == target_hash[1] &&
                state[2] == target_hash[2] && state[3] == target_hash[3]) {
                *result_index = gid;
            }
        }
        """
        p_src = ctypes.c_char_p(md5_src)
        p_len = ctypes.c_size_t(len(md5_src))
        prog_m = cl.clCreateProgramWithSource(ctx, 1, ctypes.byref(p_src), ctypes.byref(p_len), ctypes.byref(err))
        cl.clBuildProgram(prog_m, 1, (ctypes.c_void_p * 1)(dev), None, None, None)
        self._kernel_md5 = cl.clCreateKernel(prog_m, b"test_md5", ctypes.byref(err))

    def test_batch_sha256(self, passwords: List[str], salt: bytes, target_hash: bytes) -> Optional[str]:
        """Prueba un lote de contraseñas contra SHA-256 en GPU liberando la VRAM al terminar."""
        if not self.available or not passwords:
            return None

        cl = self._cl
        ctx = self._ctx
        queue = self._queue
        kernel = self._kernel_sha256
        err = ctypes.c_int32()

        n = len(passwords)
        pw_buf = bytearray(n * 64)
        lengths = (ctypes.c_uint * n)()

        for i, pwd in enumerate(passwords):
            raw = pwd.encode("utf-8", errors="ignore")[:55]
            lengths[i] = len(raw)
            pw_buf[i * 64 : i * 64 + len(raw)] = raw

        buf_pw = buf_len = buf_salt = buf_target = buf_res = None
        try:
            buf_pw = ctypes.c_void_p(cl.clCreateBuffer(ctx, 33, len(pw_buf), (ctypes.c_char * len(pw_buf)).from_buffer(pw_buf), ctypes.byref(err)))
            buf_len = ctypes.c_void_p(cl.clCreateBuffer(ctx, 33, ctypes.sizeof(lengths), ctypes.byref(lengths), ctypes.byref(err)))

            salt_bytes = (ctypes.c_char * len(salt)).from_buffer_copy(salt)
            buf_salt = ctypes.c_void_p(cl.clCreateBuffer(ctx, 33, len(salt), ctypes.byref(salt_bytes), ctypes.byref(err)))

            target_words = list(struct.unpack(">8I", target_hash[:32]))
            target_arr = (ctypes.c_uint * 8)(*target_words)
            buf_target = ctypes.c_void_p(cl.clCreateBuffer(ctx, 33, ctypes.sizeof(target_arr), ctypes.byref(target_arr), ctypes.byref(err)))

            res_idx = ctypes.c_int32(-1)
            buf_res = ctypes.c_void_p(cl.clCreateBuffer(ctx, 33, ctypes.sizeof(res_idx), ctypes.byref(res_idx), ctypes.byref(err)))

            cl.clSetKernelArg(kernel, 0, ctypes.sizeof(ctypes.c_void_p), ctypes.byref(buf_pw))
            cl.clSetKernelArg(kernel, 1, ctypes.sizeof(ctypes.c_void_p), ctypes.byref(buf_len))
            cl.clSetKernelArg(kernel, 2, ctypes.sizeof(ctypes.c_void_p), ctypes.byref(buf_salt))
            salt_len_arg = ctypes.c_uint(len(salt))
            cl.clSetKernelArg(kernel, 3, ctypes.sizeof(salt_len_arg), ctypes.byref(salt_len_arg))
            cl.clSetKernelArg(kernel, 4, ctypes.sizeof(ctypes.c_void_p), ctypes.byref(buf_target))
            cl.clSetKernelArg(kernel, 5, ctypes.sizeof(ctypes.c_void_p), ctypes.byref(buf_res))
            count_arg = ctypes.c_uint(n)
            cl.clSetKernelArg(kernel, 6, ctypes.sizeof(count_arg), ctypes.byref(count_arg))

            global_ws = (ctypes.c_size_t * 1)(n)
            cl.clEnqueueNDRangeKernel(queue, kernel, 1, None, global_ws, None, 0, None, None)
            cl.clFinish(queue)

            cl.clEnqueueReadBuffer(queue, buf_res, 1, 0, ctypes.sizeof(res_idx), ctypes.byref(res_idx), 0, None, None)

            if res_idx.value != -1 and 0 <= res_idx.value < n:
                return passwords[res_idx.value]
            return None
        finally:
            for b in (buf_pw, buf_len, buf_salt, buf_target, buf_res):
                if b is not None and b.value:
                    cl.clReleaseMemObject(b)

    def test_batch_md5(self, passwords: List[str], target_hash: bytes) -> Optional[str]:
        """Prueba un lote de contraseñas contra MD5 en GPU liberando la VRAM al terminar."""
        if not self.available or not passwords:
            return None

        cl = self._cl
        ctx = self._ctx
        queue = self._queue
        kernel = self._kernel_md5
        err = ctypes.c_int32()

        n = len(passwords)
        pw_buf = bytearray(n * 64)
        lengths = (ctypes.c_uint * n)()

        for i, pwd in enumerate(passwords):
            raw = pwd.encode("utf-8", errors="ignore")[:55]
            lengths[i] = len(raw)
            pw_buf[i * 64 : i * 64 + len(raw)] = raw

        buf_pw = buf_len = buf_target = buf_res = None
        try:
            buf_pw = ctypes.c_void_p(cl.clCreateBuffer(ctx, 33, len(pw_buf), (ctypes.c_char * len(pw_buf)).from_buffer(pw_buf), ctypes.byref(err)))
            buf_len = ctypes.c_void_p(cl.clCreateBuffer(ctx, 33, ctypes.sizeof(lengths), ctypes.byref(lengths), ctypes.byref(err)))

            target_words = list(struct.unpack("<4I", target_hash[:16]))
            target_arr = (ctypes.c_uint * 4)(*target_words)
            buf_target = ctypes.c_void_p(cl.clCreateBuffer(ctx, 33, ctypes.sizeof(target_arr), ctypes.byref(target_arr), ctypes.byref(err)))

            res_idx = ctypes.c_int32(-1)
            buf_res = ctypes.c_void_p(cl.clCreateBuffer(ctx, 33, ctypes.sizeof(res_idx), ctypes.byref(res_idx), ctypes.byref(err)))

            cl.clSetKernelArg(kernel, 0, ctypes.sizeof(ctypes.c_void_p), ctypes.byref(buf_pw))
            cl.clSetKernelArg(kernel, 1, ctypes.sizeof(ctypes.c_void_p), ctypes.byref(buf_len))
            cl.clSetKernelArg(kernel, 2, ctypes.sizeof(ctypes.c_void_p), ctypes.byref(buf_target))
            cl.clSetKernelArg(kernel, 3, ctypes.sizeof(ctypes.c_void_p), ctypes.byref(buf_res))
            count_arg = ctypes.c_uint(n)
            cl.clSetKernelArg(kernel, 4, ctypes.sizeof(count_arg), ctypes.byref(count_arg))

            global_ws = (ctypes.c_size_t * 1)(n)
            cl.clEnqueueNDRangeKernel(queue, kernel, 1, None, global_ws, None, 0, None, None)
            cl.clFinish(queue)

            cl.clEnqueueReadBuffer(queue, buf_res, 1, 0, ctypes.sizeof(res_idx), ctypes.byref(res_idx), 0, None, None)

            if res_idx.value != -1 and 0 <= res_idx.value < n:
                return passwords[res_idx.value]
            return None
        finally:
            for b in (buf_pw, buf_len, buf_target, buf_res):
                if b is not None and b.value:
                    cl.clReleaseMemObject(b)


# Instancia única del acelerador GPU
GLOBAL_GPU = GPUAccelerator()


# =====================================================================
# PERFIL CRIPTOGRÁFICO DE ARCHIVO (PDF / EXCEL)
# =====================================================================
@dataclass
class CryptoProfile:
    kind: str
    algorithm: str
    is_encrypted: bool
    salt: bytes = b""
    target_hash: bytes = b""
    revision: int = 0
    can_use_gpu: bool = False
    details: str = ""
    raw_params: dict = field(default_factory=dict)


def extract_crypto_profile(source: Path) -> CryptoProfile:
    """Extrae los parámetros criptográficos una sola vez para verificar claves sin parsear el archivo."""
    source = source.resolve()
    suffix = source.suffix.lower()

    if suffix in PDF_EXTENSIONS:
        try:
            import pypdf
        except ImportError:
            raise RuntimeError("Falta la biblioteca 'pypdf'. Ejecuta: pip install pypdf")

        reader = pypdf.PdfReader(str(source))
        if not reader.is_encrypted:
            return CryptoProfile(kind="PDF", algorithm="NONE", is_encrypted=False, details="No cifrado")

        enc = reader.trailer.get("/Encrypt")
        if not enc:
            return CryptoProfile(kind="PDF", algorithm="UNKNOWN", is_encrypted=True)

        enc_dict = enc.get_object()
        r = int(enc_dict.get("/R", 0))
        v = int(enc_dict.get("/V", 0))
        length = int(enc_dict.get("/Length", 40))

        u_obj = enc_dict.raw_get("/U")
        if hasattr(u_obj, "original_bytes"):
            u_bytes = u_obj.original_bytes
        elif isinstance(u_obj, bytes):
            u_bytes = bytes(u_obj)
        else:
            u_bytes = str(u_obj).encode("utf-8", errors="replace")

        if r == 5:
            # PDF Revision 5 (AES-256): SHA-256 directo con 8 bytes de salt (u[32:40])
            salt = u_bytes[32:40]
            target = u_bytes[:32]
            return CryptoProfile(
                kind="PDF",
                algorithm="PDF_R5_SHA256",
                is_encrypted=True,
                salt=salt,
                target_hash=target,
                revision=r,
                can_use_gpu=True,
                details="AES-256 (Revision 5 - SHA-256 Acelerable en GPU)",
                raw_params={"R": r, "V": v, "Length": length, "U": u_bytes},
            )

        elif r == 6:
            # PDF Revision 6 (AES-256 Hardened ISO 32000-2): Ciclo CBC + Multi-hash
            salt = u_bytes[32:40]
            target = u_bytes[:32]
            return CryptoProfile(
                kind="PDF",
                algorithm="PDF_R6_AES_MULTI",
                is_encrypted=True,
                salt=salt,
                target_hash=target,
                revision=r,
                can_use_gpu=False,
                details="AES-256 Hardened (Revision 6 - CPU Multi-núcleo)",
                raw_params={"R": r, "V": v, "Length": length, "U": u_bytes},
            )

        elif r in (2, 3, 4):
            # PDF Revision 2 (RC4 40-bit) / Revision 3-4 (RC4 / AES-128 con MD5)
            target = u_bytes[:16]
            o_obj = enc_dict.raw_get("/O")
            if hasattr(o_obj, "original_bytes"):
                o_bytes = o_obj.original_bytes
            elif isinstance(o_obj, bytes):
                o_bytes = bytes(o_obj)
            else:
                o_bytes = str(o_obj).encode("utf-8", errors="replace")

            id_entry = b""
            if "/ID" in reader.trailer:
                try:
                    id_entry = reader.trailer["/ID"][0].original_bytes
                except Exception:
                    try:
                        id_entry = bytes(reader.trailer["/ID"][0])
                    except Exception:
                        id_entry = b""

            p_val = int(enc_dict.get("/P", 0))
            meta_enc = bool(enc_dict.get("/EncryptMetadata", True))

            return CryptoProfile(
                kind="PDF",
                algorithm=f"PDF_R{r}_MD5",
                is_encrypted=True,
                salt=o_bytes,
                target_hash=target,
                revision=r,
                can_use_gpu=False,
                details=f"Revision {r} ({length}-bit - Multiproceso CPU Acelerado)",
                raw_params={
                    "R": r,
                    "V": v,
                    "Length": length,
                    "U": u_bytes,
                    "O": o_bytes,
                    "P": p_val,
                    "ID1": id_entry,
                    "EncryptMetadata": meta_enc,
                },
            )

        return CryptoProfile(kind="PDF", algorithm="UNKNOWN", is_encrypted=True, revision=r)

    elif suffix in EXCEL_EXTENSIONS:
        try:
            import msoffcrypto
            with source.open("rb") as f:
                office_file = msoffcrypto.OfficeFile(f)
                if not office_file.is_encrypted():
                    return CryptoProfile(kind="Excel", algorithm="NONE", is_encrypted=False, details="No cifrado")
                return CryptoProfile(
                    kind="Excel",
                    algorithm="EXCEL_OFFICE",
                    is_encrypted=True,
                    can_use_gpu=False,
                    details="Microsoft Office Agile/Standard Encryption",
                )
        except ImportError:
            return CryptoProfile(
                kind="Excel",
                algorithm="EXCEL_OFFICE_NO_LIB",
                is_encrypted=True,
                can_use_gpu=False,
                details="Requiere 'msoffcrypto-tool' instalado",
            )

    return CryptoProfile(kind="desconocido", algorithm="UNKNOWN", is_encrypted=False)


# =====================================================================
# VARIABLES GLOBALES Y TRABAJADORES CPU
# =====================================================================
_WORKER_PROFILE: Optional[CryptoProfile] = None
_WORKER_FILE_BYTES: bytes = b""
_WORKER_OFFICE_OBJ = None


def _init_cpu_worker(profile: CryptoProfile, file_bytes: bytes) -> None:
    """Inicializa cada proceso worker una sola vez en memoria RAM."""
    global _WORKER_PROFILE, _WORKER_FILE_BYTES, _WORKER_OFFICE_OBJ
    _WORKER_PROFILE = profile
    _WORKER_FILE_BYTES = file_bytes

    if profile.kind == "Excel":
        try:
            import msoffcrypto
            _WORKER_OFFICE_OBJ = msoffcrypto.OfficeFile(io.BytesIO(file_bytes))
        except Exception:
            _WORKER_OFFICE_OBJ = None


def _cpu_test_batch(batch: List[str]) -> Optional[str]:
    """Prueba un lote de contraseñas a nivel puramente criptográfico en CPU."""
    prof = _WORKER_PROFILE
    if prof is None:
        return None

    if prof.algorithm == "PDF_R6_AES_MULTI":
        try:
            from pypdf._encryption import AlgV5
            salt = prof.salt
            target = prof.target_hash
            r = prof.revision
            for pwd in batch:
                if AlgV5.calculate_hash(r, pwd.encode("utf-8", errors="ignore")[:127], salt, b"") == target:
                    return pwd
        except Exception:
            pass

    elif prof.algorithm.startswith("PDF_R") and prof.revision in (2, 3, 4):
        try:
            from pypdf._encryption import AlgV4
            r = prof.revision
            params = prof.raw_params
            key_size = params["Length"]
            o_entry = params["O"]
            u_entry = params["U"]
            p_val = params["P"]
            id1 = params["ID1"]
            meta_enc = params["EncryptMetadata"]
            for pwd in batch:
                if AlgV4.verify_user_password(
                    pwd.encode("utf-8", errors="ignore")[:32],
                    r,
                    key_size,
                    o_entry,
                    u_entry,
                    p_val,
                    id1,
                    meta_enc,
                ):
                    return pwd
        except Exception:
            pass

    elif prof.kind == "PDF":
        try:
            import pypdf
            stream = io.BytesIO(_WORKER_FILE_BYTES)
            reader = pypdf.PdfReader(stream)
            for pwd in batch:
                try:
                    if reader.decrypt(pwd) > 0:
                        return pwd
                except Exception:
                    continue
        except Exception:
            pass

    elif prof.kind == "Excel" and _WORKER_OFFICE_OBJ is not None:
        load_key = _WORKER_OFFICE_OBJ.load_key
        for pwd in batch:
            try:
                load_key(password=pwd, verify_password=True)
                return pwd
            except Exception:
                continue

    return None


# =====================================================================
# UTILIDADES DE ARCHIVOS Y DIRECTORIOS
# =====================================================================
def ensure_directories() -> None:
    for directory in (INPUT_DIR, OUTPUT_DIR, PASSWORDS_DIR, HISTORY_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def timestamp() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def file_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in PDF_EXTENSIONS:
        return "PDF"
    if suffix in EXCEL_EXTENSIONS:
        return "Excel"
    return "desconocido"


def supported_files(directory: Path) -> list[Path]:
    return sorted(
        (item for item in directory.iterdir() if item.is_file() and item.suffix.lower() in SUPPORTED_EXTENSIONS),
        key=lambda item: item.name.lower(),
    )


def text_files(directory: Path) -> list[Path]:
    return sorted(
        (item for item in directory.iterdir() if item.is_file() and item.suffix.lower() == ".txt"),
        key=lambda item: item.name.lower(),
    )


def choose_from(items: list[Path], title: str) -> Path | None:
    if not items:
        print("No hay archivos disponibles.")
        return None

    print(f"\n{title}")
    for index, item in enumerate(items, start=1):
        print(f"  {index}. {item.name}")
    print("  0. Cancelar")

    while True:
        value = input("Selecciona una opción: ").strip()
        if value == "0":
            return None
        try:
            selected = int(value)
        except ValueError:
            print("Escribe un número válido.")
            continue
        if 1 <= selected <= len(items):
            return items[selected - 1]
        print("La opción no existe.")


def unique_output_path(source: Path) -> Path:
    candidate = OUTPUT_DIR / source.name
    if not candidate.exists():
        return candidate
    stem, suffix = source.stem, source.suffix
    counter = 2
    while True:
        candidate = OUTPUT_DIR / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def count_file_lines(path: Path) -> int:
    """Cuenta líneas no vacías de forma exacta y rápida por bloques binarios."""
    count = 0
    last_byte = b"\n"
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            count += chunk.count(b"\n")
            last_byte = chunk[-1:]
    if last_byte not in (b"\n", b"\r", b""):
        count += 1
    return count


def stream_password_batches(
    password_source: Union[Path, range],
    batch_size: int = 65536,
    zero_pad: int = 0,
) -> Iterator[List[str]]:
    """Generador polimórfico que entrega lotes de contraseñas desde un TXT o desde un range numérico en RAM."""
    batch: List[str] = []

    if isinstance(password_source, Path):
        with password_source.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                pwd = line.strip()
                if pwd:
                    batch.append(pwd)
                    if len(batch) >= batch_size:
                        yield batch
                        batch = []
    elif isinstance(password_source, range):
        if zero_pad > 0:
            fmt = f"{{:0{zero_pad}d}}".format
            for num in password_source:
                batch.append(fmt(num))
                if len(batch) >= batch_size:
                    yield batch
                    batch = []
        else:
            for num in password_source:
                batch.append(str(num))
                if len(batch) >= batch_size:
                    yield batch
                    batch = []
    else:
        raise TypeError("password_source debe ser un objeto Path o range.")

    if batch:
        yield batch


def password_hash(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def write_history(record: dict[str, object]) -> None:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    with HISTORY_FILE.open("a", encoding="utf-8") as history:
        history.write(json.dumps(record, ensure_ascii=False) + "\n")


def save_password_sidecar(output_path: Path, password: str) -> Path:
    sidecar = output_path.with_name(output_path.name + ".password.txt")
    sidecar.write_text(password + "\n", encoding="utf-8")
    return sidecar


# =====================================================================
# DESBLOQUEO FINAL Y GUARDADO DEL ARCHIVO
# =====================================================================
def unlock_file(source: Path, password: str, save_password: bool = False) -> Path:
    source = source.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"No existe el archivo: {source}")
    if source.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError("Solo se admiten PDF, XLS, XLSX, XLSM, XLTX y XLTM.")

    output = unique_output_path(source)
    try:
        if source.suffix.lower() in PDF_EXTENSIONS:
            unlocked = False
            try:
                import pypdf
                reader = pypdf.PdfReader(source)
                if reader.is_encrypted:
                    res = reader.decrypt(password)
                    if res == 0:
                        raise ValueError("Contraseña incorrecta para el PDF.")
                writer = pypdf.PdfWriter()
                for page in reader.pages:
                    writer.add_page(page)
                if reader.metadata:
                    writer.add_metadata(reader.metadata)
                with output.open("wb") as f_out:
                    writer.write(f_out)
                unlocked = True
            except Exception:
                try:
                    import pikepdf
                    with pikepdf.open(source, password=password) as pdf:
                        pdf.save(output)
                    unlocked = True
                except Exception as exc2:
                    raise RuntimeError(f"No se pudo descifrar el PDF: {exc2}")

            if not unlocked:
                raise RuntimeError("No se pudo desbloquear el archivo PDF.")

        else:
            try:
                import msoffcrypto
            except ImportError as exc:
                raise RuntimeError("Falta 'msoffcrypto-tool'. Ejecuta: pip install msoffcrypto-tool") from exc

            with source.open("rb") as encrypted_file:
                office_file = msoffcrypto.OfficeFile(encrypted_file)
                if office_file.is_encrypted():
                    office_file.load_key(password=password, verify_password=True)
                    with output.open("wb") as decrypted_file:
                        office_file.decrypt(decrypted_file)
                else:
                    shutil.copy2(source, output)

        record: dict[str, object] = {
            "fecha": timestamp(),
            "resultado": "exitoso",
            "tipo": file_kind(source),
            "entrada": relative_path(source),
            "salida": relative_path(output),
            "contrasena": password,
            "hash_sha256_contrasena": password_hash(password),
            "contrasena_guardada": save_password,
        }
        if save_password:
            record["archivo_contrasena"] = relative_path(save_password_sidecar(output, password))
        write_history(record)
        return output
    except Exception:
        if output.exists():
            output.unlink()
        raise


# =====================================================================
# MOTOR MAESTRO DE FUERZA BRUTA (GPU + CPU STREAMING)
# =====================================================================
def try_unlock_with_passwords(
    source: Path,
    password_source: Union[Path, range],
    save_password: bool = False,
    verbose: bool = True,
    gpu_mode: str = "auto",  # 'auto', 'on', 'off'
    progress_callback=None,
    zero_pad: int = 0,
) -> Tuple[Optional[Path], Optional[str]]:
    source = source.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"No existe el archivo: {source}")

    # Validar y preparar fuente de contraseñas (Archivo TXT vs Rango Numérico)
    if isinstance(password_source, Path):
        if not password_source.is_file():
            raise FileNotFoundError(f"No existe el archivo de contraseñas: {password_source}")
        total_passwords = count_file_lines(password_source)
        source_label = f"'{password_source.name}'"
    elif isinstance(password_source, range):
        total_passwords = len(password_source)
        pad_info = f" (relleno {zero_pad} dígitos)" if zero_pad > 0 else ""
        source_label = f"Rango numérico {password_source.start:,} a {password_source.stop - 1:,}{pad_info}"
    else:
        raise TypeError("password_source debe ser un Path (archivo .txt) o un range numérico.")

    # Extraer perfil criptográfico
    profile = extract_crypto_profile(source)
    if not profile.is_encrypted:
        if verbose:
            print("[i] El archivo no está protegido con contraseña. Copiando directamente...")
        out = unlock_file(source, "", save_password=save_password)
        return out, ""

    if total_passwords == 0:
        raise ValueError("La fuente de contraseñas está vacía.")

    # Selección del motor óptimo (GPU vs CPU)
    use_gpu = False
    if gpu_mode in ("auto", "on"):
        if GLOBAL_GPU.available and profile.can_use_gpu:
            use_gpu = True
        elif gpu_mode == "on" and not GLOBAL_GPU.available:
            if verbose:
                print("[!] Aviso: GPU forzada pero no está disponible. Usando CPU.")

    engine_desc = f"GPU ({GLOBAL_GPU.device_name})" if use_gpu else f"CPU ({os.cpu_count() or 4} núcleos)"

    if verbose:
        print(f"\n{'='*70}")
        print(f"[*] Archivo objetivo    : {source.name} [{profile.details}]")
        print(f"[*] Contraseñas a probar: {total_passwords:,} desde {source_label}")
        print(f"[*] Motor activo        : {engine_desc}")
        print(f"{'='*70}\n")

    start_time = time.perf_counter()
    tested = 0
    found_password: Optional[str] = None

    if use_gpu:
        # -------------------------------------------------------------
        # VÍA GPU: Evaluación masiva por bloques en VRAM (millones/segundo)
        # -------------------------------------------------------------
        batch_size = 65536
        for batch in stream_password_batches(password_source, batch_size=batch_size, zero_pad=zero_pad):
            match = None
            if profile.algorithm == "PDF_R5_SHA256":
                match = GLOBAL_GPU.test_batch_sha256(batch, profile.salt, profile.target_hash)

            tested += len(batch)

            elapsed = time.perf_counter() - start_time
            speed = tested / elapsed if elapsed > 0 else 0

            if verbose:
                pct = min(100.0, (tested / total_passwords) * 100)
                print(
                    f"[{tested:,}/{total_passwords:,}] ({pct:.1f}%) | "
                    f"Velocidad: {speed:,.0f} claves/s | Motor: GPU",
                    end="\r",
                    flush=True,
                )

            if progress_callback:
                progress_callback(tested, total_passwords, speed, match)

            if match is not None:
                found_password = match
                break

    else:
        # -------------------------------------------------------------
        # VÍA CPU: Multiprocesamiento optimizado en RAM
        # -------------------------------------------------------------
        workers = os.cpu_count() or 4
        file_bytes = source.read_bytes()
        batch_size = 1000 if profile.algorithm == "PDF_R6_AES_MULTI" else 5000

        with ProcessPoolExecutor(
            max_workers=workers,
            initializer=_init_cpu_worker,
            initargs=(profile, file_bytes),
        ) as executor:
            batch_gen = stream_password_batches(password_source, batch_size=batch_size, zero_pad=zero_pad)
            active_futures = set()
            max_in_flight = workers * 3

            def schedule_more():
                while len(active_futures) < max_in_flight:
                    try:
                        b = next(batch_gen)
                        fut = executor.submit(_cpu_test_batch, b)
                        fut._batch_len = len(b)  # type: ignore
                        active_futures.add(fut)
                    except StopIteration:
                        break

            schedule_more()

            while active_futures:
                done = set()
                for fut in as_completed(active_futures):
                    done.add(fut)
                    b_len = getattr(fut, "_batch_len", 0)
                    tested += b_len
                    res = fut.result()

                    elapsed = time.perf_counter() - start_time
                    speed = tested / elapsed if elapsed > 0 else 0

                    if res is not None:
                        found_password = res
                        for f in active_futures:
                            f.cancel()
                        active_futures.clear()
                        if progress_callback:
                            progress_callback(tested, total_passwords, speed, res)
                        break

                    if verbose:
                        pct = min(100.0, (tested / total_passwords) * 100)
                        print(
                            f"[{tested:,}/{total_passwords:,}] ({pct:.1f}%) | "
                            f"Velocidad: {speed:,.0f} claves/s | Motor: CPU",
                            end="\r",
                            flush=True,
                        )

                    if progress_callback:
                        progress_callback(tested, total_passwords, speed, None)
                    break

                active_futures.difference_update(done)
                if found_password is None:
                    schedule_more()

    elapsed_total = time.perf_counter() - start_time
    avg_speed = tested / elapsed_total if elapsed_total > 0 else 0

    if found_password is not None:
        if verbose:
            print(" " * 80, end="\r")
            print(f"[+] ¡ÉXITO en {elapsed_total:.2f}s! ({avg_speed:,.0f} claves/s)")
            print(f"[+] Contraseña encontrada: '{found_password}'")
        output = unlock_file(source, found_password, save_password=save_password)
        if verbose:
            print(f"[+] Archivo desbloqueado guardado en: {output}")
        return output, found_password

    if verbose:
        print(" " * 80, end="\r")
        print(f"[-] No se encontró la clave tras probar {tested:,} combinaciones en {elapsed_total:.2f}s.")

    return None, None


# =====================================================================
# BENCHMARK DE VELOCIDAD DE HARDWARE (GPU VS CPU)
# =====================================================================
def _cpu_bench_worker(args: Tuple[List[str], bytes, bytes]) -> Optional[str]:
    batch, salt, target = args
    for p in batch:
        if hashlib.sha256(p.encode("utf-8") + salt).digest() == target:
            return p
    return None


def run_benchmark() -> Tuple[float, float, float, float]:
    print("\n" + "=" * 60)
    print("      BENCHMARK DE RENDIMIENTO (GPU vs CPU)")
    print("=" * 60)

    N = 1_000_000
    salt = b"benchmark_salt12"
    secret = "pwd_benchmark_target"
    target = hashlib.sha256(secret.encode() + salt).digest()

    passwords = [f"test_pwd_{i}" for i in range(N - 1)] + [secret]

    elapsed_gpu, rate_gpu = 0.0, 0.0
    if GLOBAL_GPU.available:
        print(f"\n[1] Probando GPU: {GLOBAL_GPU.device_name}...")
        t0 = time.perf_counter()
        found = GLOBAL_GPU.test_batch_sha256(passwords, salt, target)
        t1 = time.perf_counter()
        elapsed_gpu = t1 - t0
        rate_gpu = N / elapsed_gpu if elapsed_gpu > 0 else 0
        status = "Éxito" if found == secret else "Fallo"
        print(f"    - Tiempo GPU   : {elapsed_gpu:.4f} s ({status})")
        print(f"    - Rendimiento  : {rate_gpu:,.0f} claves/segundo")
    else:
        print("\n[1] GPU no disponible en este sistema.")

    workers = os.cpu_count() or 4
    print(f"\n[2] Probando CPU: {workers} núcleos...")
    t0 = time.perf_counter()
    chunk_size = max(1, len(passwords) // workers)
    chunks = [passwords[i : i + chunk_size] for i in range(0, len(passwords), chunk_size)]

    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(_cpu_bench_worker, (ch, salt, target)) for ch in chunks]
        for f in futs:
            f.result()
    t1 = time.perf_counter()
    elapsed_cpu = t1 - t0
    rate_cpu = N / elapsed_cpu if elapsed_cpu > 0 else 0
    print(f"    - Tiempo CPU   : {elapsed_cpu:.4f} s")
    print(f"    - Rendimiento  : {rate_cpu:,.0f} claves/segundo")

    if GLOBAL_GPU.available and rate_cpu > 0:
        speedup = rate_gpu / rate_cpu
        print(f"\n[+] ¡La GPU es {speedup:.1f} veces más rápida que la CPU en tu equipo!")
    print("=" * 60 + "\n")

    return elapsed_gpu, rate_gpu, elapsed_cpu, rate_cpu


# =====================================================================
# MODOS INTERACTIVOS (CONSOLA)
# =====================================================================
def ask_save_password() -> bool:
    answer = input("¿Guardar también la contraseña en un TXT junto al archivo desbloqueado? (s/N): ").strip().lower()
    return answer in {"s", "si", "sí", "y", "yes"}


def unlock_interactive(source: Path | None = None, password: str | None = None) -> None:
    source = source or choose_from(supported_files(INPUT_DIR), "Archivos en por_desbloquear")
    if source is None:
        return
    if password is None:
        password = getpass.getpass("Contraseña conocida (Enter si no tiene): ")
    try:
        output = unlock_file(source, password, save_password=ask_save_password())
    except Exception as exc:
        print(f"No se pudo desbloquear: {exc}")
        return
    print(f"Archivo guardado en: {output}")


def unlock_from_password_txt() -> None:
    source = choose_from(supported_files(INPUT_DIR), "Archivo que se va a desbloquear")
    if source is None:
        return
    password_file = choose_from(text_files(PASSWORDS_DIR), "TXT de Contraseñas")
    if password_file is None:
        return

    try:
        out, found_pwd = try_unlock_with_passwords(source, password_file, save_password=ask_save_password())
        if found_pwd is not None:
            print(f"[+] Contraseña encontrada: '{found_pwd}'")
    except Exception as exc:
        print(f"Error durante el desbloqueo: {exc}")


def Numbers() -> None:
    source = choose_from(supported_files(INPUT_DIR), "Archivo que se va a desbloquear")
    if source is None:
        return

    raw_start = input("Número inicial (Enter para 0): ").strip()
    start_num = int(raw_start) if raw_start.isdigit() else 0

    raw_max = input("Límite superior (Enter para 1,000,000,000): ").strip()
    max_num = int(raw_max) if raw_max.isdigit() else 1_000_000_000

    if max_num <= start_num:
        print("El límite superior debe ser mayor que el número inicial.")
        return

    raw_pad = input("¿Fijar longitud con ceros a la izquierda, ej. 4 para '0001'? (Enter o 0 = sin relleno): ").strip()
    zero_pad = int(raw_pad) if raw_pad.isdigit() else 0

    password_number = range(start_num, max_num)

    try:
        out, found_pwd = try_unlock_with_passwords(
            source,
            password_number,
            save_password=ask_save_password(),
            zero_pad=zero_pad,
        )
        if found_pwd is not None:
            print(f"[+] Contraseña encontrada: '{found_pwd}'")
    except Exception as exc:
        print(f"Error durante el desbloqueo: {exc}")


def add_password_txt() -> None:
    raw_path = input("Ruta del archivo .txt que contiene contraseñas: ").strip().strip('"')
    source = Path(raw_path).expanduser()
    if not source.is_file() or source.suffix.lower() != ".txt":
        print("La ruta no es un archivo .txt válido.")
        return
    lines = count_file_lines(source)
    destination = PASSWORDS_DIR / source.name
    if destination.exists():
        destination = PASSWORDS_DIR / f"{source.stem}_copia{source.suffix}"
    shutil.copy2(source, destination)
    print(f"Copiado a: {destination} ({lines:,} líneas detectadas)")


def show_history() -> None:
    if not HISTORY_FILE.exists():
        print("Todavía no hay archivos procesados.")
        return
    print("\n================== HISTORIAL DE DESBLOQUEOS ==================")
    for line in HISTORY_FILE.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        clave = record.get("contrasena")
        if clave is None:
            clave = record.get("hash_sha256_contrasena", "?")
        print(
            f"- {record.get('fecha', '?')} | {record.get('tipo', '?')} | "
            f"{record.get('entrada', '?')} -> {record.get('salida', '?')} | "
            f"🔑 Clave: '{clave}'"
        )
    print("==============================================================")


def interactive_menu() -> None:
    ensure_directories()
    while True:
        gpu_status = f"{GLOBAL_GPU.device_name} (ACTIVA)" if GLOBAL_GPU.available else "No disponible"
        print(
            f"\n{'='*55}\n"
            f"  DESBLOQUEADOR ULTRA RÁPIDO (GPU & CPU)\n"
            f"  ⚡ GPU : {gpu_status}\n"
            f"  🧠 CPU : {os.cpu_count() or 4} hilos de procesamiento\n"
            f"{'='*55}\n"
            "1. Desbloquear con contraseña conocida\n"
            "2. Probar contraseñas desde un TXT y desbloquear\n"
            "3. Añadir un TXT a la carpeta Contraseñas\n"
            "4. Test de velocidad de hardware (Benchmark GPU vs CPU)\n"
            "5. Ver historial (con contraseñas visibles)\n"
            "6. Abrir interfaz interactiva Web (Streamlit)\n"
            "7. Probar contraseñas numéricas (0 a 999,999,999)\n"
            "8. Salir"
        )
        option = input("Elige una opción: ").strip()
        if option == "1":
            unlock_interactive()
        elif option == "2":
            unlock_from_password_txt()
        elif option == "3":
            add_password_txt()
        elif option == "4":
            run_benchmark()
        elif option == "5":
            show_history()
        elif option == "6":
            print("\n[*] Levantando servidor Streamlit...")
            subprocess.run([sys.executable, "-m", "streamlit", "run", str(Path(__file__).resolve())])
        elif option == "7":
            Numbers()
        elif option == "8":
            print("Hasta luego.")
            return
        else:
            print("Opción no válida.")


# =====================================================================
# MODO INTERFAZ GRÁFICA INTERACTIVA WEB (STREAMLIT)
# =====================================================================
def run_streamlit_ui() -> None:
    ensure_directories()
    import streamlit as st

    st.set_page_config(
        page_title="Desbloqueador PDF & Excel - GPU & CPU",
        page_icon="🔓",
        layout="wide",
    )

    st.title("🔓 Desbloqueador de PDF y Excel (GPU & CPU Acelerado)")
    st.caption("Recuperación y descifrado de archivos PDF y Excel con aceleración por hardware en GPU y CPU.")

    # Panel de hardware
    col_gpu, col_cpu, col_dir = st.columns(3)
    with col_gpu:
        if GLOBAL_GPU.available:
            st.success(f"⚡ **GPU Activa**: {GLOBAL_GPU.device_name}")
        else:
            st.warning("⚡ **GPU**: No detectada / Modo CPU")
    with col_cpu:
        st.info(f"🧠 **CPU**: {os.cpu_count() or 4} hilos de procesamiento")
    with col_dir:
        st.caption(f"📁 **Salida**: `{OUTPUT_DIR.resolve()}`")

    st.divider()

    tab_unlock, tab_history, tab_benchmark, tab_help = st.tabs([
        "🔓 Desbloquear Archivo",
        "📜 Historial con Contraseñas",
        "⚡ Benchmark GPU vs CPU",
        "ℹ️ Guía y Formatos"
    ])

    # -------------------------------------------------------------
    # PESTAÑA 1: DESBLOQUEO DE ARCHIVOS
    # -------------------------------------------------------------
    with tab_unlock:
        c_src, _ = st.columns([1, 1])
        with c_src:
            origen_archivo = st.radio(
                "Origen del archivo protegido:",
                ["📁 Carpeta por_desbloquear", "⬆️ Subir archivo desde mi PC", "📝 Ruta manual en disco"],
                horizontal=True
            )

        target_path: Optional[Path] = None

        if origen_archivo == "📁 Carpeta por_desbloquear":
            locales = supported_files(INPUT_DIR)
            if not locales:
                st.warning(f"No hay archivos compatibles en `{INPUT_DIR.resolve()}`. Coloca uno o súbelo en la pestaña.")
            else:
                sel_name = st.selectbox("Selecciona el archivo:", [f.name for f in locales])
                if sel_name:
                    target_path = INPUT_DIR / sel_name

        elif origen_archivo == "⬆️ Subir archivo desde mi PC":
            uploaded = st.file_uploader("Arrastra tu archivo aquí:", type=["pdf", "xlsx", "xls", "xlsm"])
            if uploaded:
                save_dest = INPUT_DIR / uploaded.name
                save_dest.write_bytes(uploaded.getvalue())
                target_path = save_dest
                st.success(f"Archivo cargado: `{uploaded.name}`")

        else:
            manual_in = st.text_input("Ingresa la ruta absoluta del archivo en tu PC:")
            if manual_in.strip():
                p_cand = Path(manual_in.strip().strip("\"'")).expanduser().resolve()
                if p_cand.is_file() and p_cand.suffix.lower() in SUPPORTED_EXTENSIONS:
                    target_path = p_cand
                else:
                    st.error("Ruta no válida o formato no compatible.")

        if target_path and target_path.is_file():
            st.markdown("---")
            profile = extract_crypto_profile(target_path)
            c1, c2, c3 = st.columns(3)
            c1.metric("Tipo", profile.kind)
            c2.metric("Tamaño", f"{target_path.stat().st_size / 1024:.1f} KB")
            c3.metric("Protegido", "🔒 Sí" if profile.is_encrypted else "🔓 No protegido")

            if profile.can_use_gpu:
                st.success(f"⚡ **Acelerable por GPU**: {profile.details} — Tu tarjeta gráfica evaluará millones de combinaciones por segundo.")
            elif profile.algorithm == "PDF_R6_AES_MULTI":
                st.info(f"🧠 **Cifrado Endurecido**: {profile.details} — Se ejecutará en paralelo aprovechando al máximo los núcleos de tu CPU.")
            else:
                st.caption(f"Detalle: {profile.details}")

            st.markdown("#### 🎯 Método de Desbloqueo")
            metodo = st.radio(
                "Selecciona cómo deseas proceder:",
                [
                    "🔍 Probar diccionario TXT (Fuerza Bruta / Recuperación)",
                    "🔢 Fuerza bruta numérica (Rango de números / PIN)",
                    "🔑 Conozco la contraseña (Desbloquear directamente)"
                ]
            )

            if metodo == "🔑 Conozco la contraseña (Desbloquear directamente)":
                col_k1, col_k2 = st.columns([2, 1])
                with col_k1:
                    pwd_in = st.text_input("Contraseña conocida:", type="password")
                with col_k2:
                    save_sidecar_k = st.checkbox("💾 Guardar contraseña en TXT junto a la salida", value=True, key="save_sidecar_k")

                if st.button("🔓 Desbloquear Archivo", type="primary", use_container_width=True):
                    try:
                        out_p = unlock_file(target_path, pwd_in, save_password=save_sidecar_k)
                        st.success(f"¡Éxito! Archivo desbloqueado guardado en:\n`{out_p}`")
                        st.download_button(
                            label="⬇️ Descargar Archivo Desbloqueado",
                            data=out_p.read_bytes(),
                            file_name=out_p.name,
                            mime="application/octet-stream",
                            use_container_width=True
                        )
                    except Exception as e:
                        st.error(f"Error al desbloquear: {e}")

            elif metodo == "🔢 Fuerza bruta numérica (Rango de números / PIN)":
                col_n1, col_n2, col_n3 = st.columns(3)
                with col_n1:
                    num_start = int(st.number_input("Desde el número:", min_value=0, max_value=999_999_999, value=0, step=1))
                with col_n2:
                    num_stop = int(st.number_input("Hasta el número (límite):", min_value=1, max_value=1_000_000_000, value=1_000_000, step=100_000))
                with col_n3:
                    zero_pad_ui = int(st.number_input("Relleno con ceros (0 = sin relleno):", min_value=0, max_value=12, value=0, step=1))

                col_eng_n, col_sav_n = st.columns(2)
                with col_eng_n:
                    motor_op_n = st.selectbox(
                        "Motor preferido:",
                        ["auto", "on", "off"],
                        format_func=lambda x: "⚡ Automático (GPU si es compatible, CPU si no)" if x == "auto" else ("⚡ Forzar GPU" if x == "on" else "🧠 Forzar CPU (Multiproceso)"),
                        index=0,
                        key="motor_num"
                    )
                with col_sav_n:
                    save_sidecar_n = st.checkbox("💾 Guardar contraseña en TXT junto a la salida", value=True, key="save_sidecar_n")

                if st.button("🚀 Iniciar Fuerza Bruta Numérica", type="primary", use_container_width=True):
                    if num_stop <= num_start:
                        st.error("El número límite debe ser mayor que el número inicial.")
                    else:
                        rango_num = range(num_start, num_stop)
                        total_claves = len(rango_num)
                        st.info(f"Evaluando {total_claves:,} combinaciones numéricas contra `{target_path.name}`...")
                        prog_bar = st.progress(0.0)
                        status_slot = st.empty()

                        def ui_progress_num(tested, total, speed, found):
                            pct = min(1.0, tested / total) if total > 0 else 0.0
                            prog_bar.progress(pct)
                            status_slot.markdown(f"**Progreso:** `{tested:,}/{total:,}` ({pct*100:.1f}%) | ⚡ **Velocidad:** `{speed:,.0f} claves/s`")

                        try:
                            out_p, found_pwd = try_unlock_with_passwords(
                                target_path,
                                rango_num,
                                save_password=save_sidecar_n,
                                verbose=False,
                                gpu_mode=motor_op_n,
                                progress_callback=ui_progress_num,
                                zero_pad=zero_pad_ui,
                            )
                            if out_p and found_pwd is not None:
                                prog_bar.progress(1.0)
                                st.balloons()
                                st.success("🎉 ¡CONTRASEÑA NUMÉRICA ENCONTRADA CON ÉXITO!")
                                st.markdown(f"### 🔑 Contraseña: `{found_pwd}`")
                                st.info(f"Archivo desbloqueado guardado en: `{out_p}`")
                                st.download_button(
                                    label="⬇️ Descargar Archivo Desbloqueado Ahora",
                                    data=out_p.read_bytes(),
                                    file_name=out_p.name,
                                    mime="application/octet-stream",
                                    use_container_width=True,
                                    key="dl_num_btn"
                                )
                            else:
                                st.error(f"No se encontró la clave entre las {total_claves:,} combinaciones numéricas probadas.")
                        except Exception as e:
                            st.error(f"Error durante el desbloqueo: {e}")

            else:
                # Probar diccionario TXT
                col_txt, col_eng = st.columns([1, 1])
                with col_txt:
                    origen_txt = st.radio(
                        "Origen del diccionario:",
                        ["📁 Carpeta Contraseñas", "⬆️ Subir archivo .txt"],
                        horizontal=True
                    )
                    txt_path: Optional[Path] = None
                    if origen_txt == "📁 Carpeta Contraseñas":
                        txts = text_files(PASSWORDS_DIR)
                        if not txts:
                            st.warning("No hay archivos .txt en la carpeta Contraseñas.")
                        else:
                            sel_txt_name = st.selectbox("Elige el diccionario:", [t.name for t in txts])
                            if sel_txt_name:
                                txt_path = PASSWORDS_DIR / sel_txt_name
                    else:
                        up_txt = st.file_uploader("Sube tu TXT de contraseñas:", type=["txt"])
                        if up_txt:
                            tmp_t = PASSWORDS_DIR / up_txt.name
                            tmp_t.write_bytes(up_txt.getvalue())
                            txt_path = tmp_t

                with col_eng:
                    motor_op = st.selectbox(
                        "Motor preferido:",
                        ["auto", "on", "off"],
                        format_func=lambda x: "⚡ Automático (GPU si es compatible, CPU si no)" if x == "auto" else ("⚡ Forzar GPU" if x == "on" else "🧠 Forzar CPU (Multiproceso)"),
                        index=0
                    )
                    save_sidecar_d = st.checkbox("💾 Guardar contraseña en TXT junto a la salida", value=True, key="save_sidecar_d")

                if st.button("🚀 Iniciar Desbloqueo por Diccionario", type="primary", use_container_width=True):
                    if not txt_path or not txt_path.is_file():
                        st.error("Selecciona o sube un archivo .txt con contraseñas.")
                    else:
                        total_claves = count_file_lines(txt_path)
                        st.info(f"Evaluando {total_claves:,} contraseñas desde `{txt_path.name}` contra `{target_path.name}`...")
                        prog_bar = st.progress(0.0)
                        status_slot = st.empty()

                        def ui_progress(tested, total, speed, found):
                            pct = min(1.0, tested / total) if total > 0 else 0.0
                            prog_bar.progress(pct)
                            status_slot.markdown(f"**Progreso:** `{tested:,}/{total:,}` ({pct*100:.1f}%) | ⚡ **Velocidad:** `{speed:,.0f} claves/s`")

                        try:
                            out_p, found_pwd = try_unlock_with_passwords(
                                target_path,
                                txt_path,
                                save_password=save_sidecar_d,
                                verbose=False,
                                gpu_mode=motor_op,
                                progress_callback=ui_progress
                            )
                            if out_p and found_pwd is not None:
                                prog_bar.progress(1.0)
                                st.balloons()
                                st.success("🎉 ¡CONTRASEÑA ENCONTRADA CON ÉXITO!")
                                st.markdown(f"### 🔑 Contraseña: `{found_pwd}`")
                                st.info(f"Archivo desbloqueado guardado en: `{out_p}`")
                                st.download_button(
                                    label="⬇️ Descargar Archivo Desbloqueado Ahora",
                                    data=out_p.read_bytes(),
                                    file_name=out_p.name,
                                    mime="application/octet-stream",
                                    use_container_width=True
                                )
                            else:
                                st.error(f"No se encontró la clave entre las {total_claves:,} contraseñas probadas.")
                        except Exception as e:
                            st.error(f"Error durante el desbloqueo: {e}")

    # -------------------------------------------------------------
    # PESTAÑA 2: HISTORIAL CON CONTRASEÑAS VISIBLES
    # -------------------------------------------------------------
    with tab_history:
        st.markdown("### 📜 Historial de Archivos Desbloqueados")
        st.caption("Registro de todos los documentos descifrados con su contraseña visible y botón de descarga.")

        if not HISTORY_FILE.exists() or HISTORY_FILE.stat().st_size == 0:
            st.info("Aún no hay archivos procesados en el historial.")
        else:
            records = []
            for line in HISTORY_FILE.read_text(encoding="utf-8").splitlines():
                try:
                    records.append(json.loads(line))
                except Exception:
                    continue

            if not records:
                st.info("No hay registros en el historial.")
            else:
                _, c_h2 = st.columns([4, 1])
                with c_h2:
                    if st.button("🗑️ Borrar Historial", use_container_width=True):
                        HISTORY_FILE.unlink(missing_ok=True)
                        st.rerun()

                for idx, r in enumerate(reversed(records), 1):
                    clave = r.get("contrasena")
                    if clave is None:
                        clave = r.get("hash_sha256_contrasena", "No registrada")
                    with st.expander(f"📁 {Path(str(r.get('entrada', ''))).name} — 🔑 Clave: `{clave}` ({r.get('fecha', '')[:19]})", expanded=(idx == 1)):
                        c_info, c_down = st.columns([3, 1])
                        with c_info:
                            st.markdown(f"**Fecha y Hora:** {r.get('fecha', '?')}")
                            st.markdown(f"**Tipo de Documento:** `{r.get('tipo', '?')}`")
                            st.markdown(f"**Archivo de Entrada:** `{r.get('entrada', '?')}`")
                            st.markdown(f"**Archivo Desbloqueado:** `{r.get('salida', '?')}`")
                            st.markdown(f"**🔑 Contraseña Encontrada:** `{clave}`")
                        with c_down:
                            out_rel = r.get("salida", "")
                            out_f = (ROOT / out_rel) if out_rel else None
                            if out_f and out_f.is_file():
                                st.download_button(
                                    label="⬇️ Descargar Copia",
                                    data=out_f.read_bytes(),
                                    file_name=out_f.name,
                                    key=f"dl_history_{idx}",
                                    use_container_width=True
                                )
                            else:
                                st.caption("Archivo físico no disponible en disco.")

    # -------------------------------------------------------------
    # PESTAÑA 3: BENCHMARK GPU VS CPU
    # -------------------------------------------------------------
    with tab_benchmark:
        st.markdown("### ⚡ Benchmark de Rendimiento de Hardware")
        st.caption("Prueba la velocidad real de procesamiento numérico de claves de tu tarjeta gráfica y procesador.")

        if st.button("▶️ Ejecutar Prueba de Velocidad (1,000,000 de contraseñas)", type="primary"):
            with st.spinner("Midiendo velocidad en GPU y CPU..."):
                t_gpu, r_gpu, t_cpu, r_cpu = run_benchmark()
                b1, b2, b3 = st.columns(3)
                with b1:
                    gpu_label = GLOBAL_GPU.device_name if GLOBAL_GPU.available else "No disponible"
                    st.metric(f"⚡ GPU ({gpu_label})", f"{r_gpu:,.0f} claves/s", f"{t_gpu:.4f} s")
                with b2:
                    st.metric(f"🧠 CPU ({os.cpu_count() or 4} hilos)", f"{r_cpu:,.0f} claves/s", f"{t_cpu:.4f} s")
                with b3:
                    if r_cpu > 0 and r_gpu > 0:
                        st.metric("🚀 Aceleración GPU", f"{r_gpu / r_cpu:.1f}x más rápida")

                st.success("¡Benchmark completado! La tarjeta gráfica procesa lotes de claves masivamente en memoria VRAM.")

    # -------------------------------------------------------------
    # PESTAÑA 4: GUÍA Y FORMATOS
    # -------------------------------------------------------------
    with tab_help:
        st.markdown("""
        ### ℹ️ Guía Rápida y Funcionamiento Interno

        #### 🚀 ¿Cómo aprovecha tu hardware?
        - **GPU (OpenCL Nativo):** Usa los controladores de video de tu tarjeta gráfica NVIDIA GeForce RTX, AMD Radeon o Intel Arc para ejecutar código C compilado en tiempo de ejecución. Puede probar millones de claves por segundo.
        - **CPU Multi-núcleo:** En PDFs con cifrados complejos o cuando no hay tarjeta gráfica disponible, se activan todos los núcleos de tu CPU en paralelo con multiprocesamiento en memoria RAM.

        #### 📄 Formatos de PDF:
        - **Cifrado Normal (Revisión 5 - AES-256):** Verificación directa mediante SHA-256. Es **100% acelerable en GPU**.
        - **Cifrado Endurecido (Revisión 6 - AES-256 Hardened ISO 32000-2):** Requiere decenas de rondas de cifrado encadenadas. Se ejecuta en paralelo sobre los núcleos de tu CPU.

        #### 📁 Estructura de Carpetas:
        - `por_desbloquear/`: Deposita aquí los PDFs o Excels que quieras desbloquear.
        - `Contraseñas/`: Carpeta para listas de contraseñas (`rockyou.txt`, `contraseña.txt`).
        - `crakeados/`: Carpeta donde se guardan los archivos desbloqueados sin contraseña.
        - `historial/`: Registro persistente en JSON con fecha, ruta y contraseña encontrada.
        """)


# =====================================================================
# CLI PARSER
# =====================================================================
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command")

    unlock_parser = subparsers.add_parser("unlock", help="desbloquear un archivo protegido")
    unlock_parser.add_argument("--file", type=Path, required=True, help="ruta del PDF o Excel protegido")
    unlock_parser.add_argument("--password-file", type=Path, help="TXT con contraseñas a probar")
    unlock_parser.add_argument("--numeric-max", type=int, help="probar números desde 0 hasta este límite (ej. 1000000000)")
    unlock_parser.add_argument("--zero-pad", type=int, default=0, help="rellenar números con ceros a la izquierda (ej. 4 para 0001)")
    unlock_parser.add_argument("--password", type=str, help="contraseña conocida")
    unlock_parser.add_argument("--gpu", choices=["auto", "on", "off"], default="auto", help="aceleración GPU (auto/on/off)")
    unlock_parser.add_argument("--record-password", action="store_true", help="guardar la contraseña en un TXT junto a la salida")

    subparsers.add_parser("history", help="mostrar el historial")
    subparsers.add_parser("benchmark", help="medir la velocidad de la GPU y la CPU")
    subparsers.add_parser("web", help="iniciar la interfaz gráfica interactiva en Streamlit")

    return parser


def is_running_in_streamlit() -> bool:
    """Detecta si el archivo fue invocado por 'streamlit run'."""
    try:
        from streamlit.runtime import exists
        return exists()
    except ImportError:
        return False


def main() -> int:
    ensure_directories()
    args = build_parser().parse_args()

    if args.command is None:
        interactive_menu()
        return 0

    if args.command == "web":
        print("[*] Iniciando interfaz interactiva Web en Streamlit...")
        subprocess.run([sys.executable, "-m", "streamlit", "run", str(Path(__file__).resolve())])
        return 0

    if args.command == "history":
        show_history()
        return 0

    if args.command == "benchmark":
        run_benchmark()
        return 0

    if args.command == "unlock":
        try:
            if args.password_file:
                out_p, _ = try_unlock_with_passwords(
                    args.file,
                    args.password_file,
                    save_password=args.record_password,
                    verbose=True,
                    gpu_mode=args.gpu,
                )
                return 0 if out_p is not None else 1
            elif args.numeric_max is not None:
                out_p, _ = try_unlock_with_passwords(
                    args.file,
                    range(0, args.numeric_max),
                    save_password=args.record_password,
                    verbose=True,
                    gpu_mode=args.gpu,
                    zero_pad=args.zero_pad,
                )
                return 0 if out_p is not None else 1
            else:
                pwd = args.password
                if pwd is None:
                    pwd = getpass.getpass("Contraseña conocida: ")
                output = unlock_file(args.file, pwd, save_password=args.record_password)
                print(f"[+] Archivo desbloqueado guardado en: {output}")
                return 0
        except Exception as exc:
            print(f"[-] Error: {exc}", file=sys.stderr)
            return 1

    return 2


if __name__ == "__main__":
    mp.freeze_support()
    if is_running_in_streamlit():
        run_streamlit_ui()
    else:
        raise SystemExit(main())