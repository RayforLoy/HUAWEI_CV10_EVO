"""Extract the neutral CF20 grip model from a locally supplied Huawei VR Home APK.

Install UnityPy==1.25.4 and numpy in a local environment. Run with the path to
com.huawei.vrlauncherx 11.1.0.337 and the desired output .glb path. Geometry,
textures and the resulting GLB belong to the input sample.
"""

import argparse
import hashlib
import io
import json
import re
import struct
import zipfile
from pathlib import Path

import numpy as np
import UnityPy
from UnityPy.helpers.MeshHelper import MeshHandler


SOURCE_SHA256 = "1e91f00d596c636c3f52dddc494ee6b745cdf90bb3a0838ff203f9ae54b92dd3"
DATA = "assets/bin/Data/"
PARTS = ("c_b", "c_f", "b_l", "b_r", "c_t", "v_m")


def read_asset(apk, name):
    path = DATA + name
    if path in apk.namelist():
        return apk.read(path)
    parts = [k for k in apk.namelist() if re.fullmatch(re.escape(path) + r"\.split\d+", k)]
    if not parts:
        raise ValueError(f"No asset {path}")
    return b"".join(apk.read(k) for k in sorted(parts, key=lambda k: int(k.rsplit("split", 1)[1])))


def xyz(vector):
    return [vector.x, vector.y, vector.z]


def local_matrix(transform):
    q = transform.m_LocalRotation
    x, y, z, w = np.array([q.x, q.y, q.z, q.w]) / np.linalg.norm([q.x, q.y, q.z, q.w])
    rotation = np.array([
        [1 - 2*(y*y + z*z), 2*(x*y - z*w), 2*(x*z + y*w)],
        [2*(x*y + z*w), 1 - 2*(x*x + z*z), 2*(y*z - x*w)],
        [2*(x*z - y*w), 2*(y*z + x*w), 1 - 2*(x*x + y*y)],
    ])
    matrix = np.eye(4)
    matrix[:3, :3] = rotation @ np.diag(xyz(transform.m_LocalScale))
    matrix[:3, 3] = xyz(transform.m_LocalPosition)
    return matrix


class Glb:
    def __init__(self):
        self.bin = bytearray()
        self.doc = {
            "asset": {"version": "2.0", "generator": "CV10 OEM model extractor"},
            "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"name": "CF20", "mesh": 0}],
            "meshes": [{"name": "CF20", "primitives": []}], "materials": [],
            "textures": [], "images": [], "bufferViews": [], "accessors": [],
        }

    def view(self, raw, **fields):
        self.bin.extend(b"\0" * (-len(self.bin) % 4))
        index = len(self.doc["bufferViews"])
        self.doc["bufferViews"].append({"buffer": 0, "byteOffset": len(self.bin), "byteLength": len(raw), **fields})
        self.bin.extend(raw)
        return index

    def accessor(self, values, gl_type, shape, target, bounds=False):
        index = len(self.doc["accessors"])
        raw = values.astype("<u2" if gl_type == 5123 else "<f4")
        acc = {"bufferView": self.view(raw.tobytes(), target=target), "componentType": gl_type,
               "type": shape, "count": len(raw)}
        if bounds:
            acc.update(min=raw.min(axis=0).tolist(), max=raw.max(axis=0).tolist())
        self.doc["accessors"].append(acc)
        return index

    def encode(self):
        self.doc["buffers"] = [{"byteLength": len(self.bin)}]
        descriptor = json.dumps(self.doc, separators=(",", ":"), allow_nan=False).encode()
        descriptor += b" " * (-len(descriptor) % 4)
        payload = bytes(self.bin) + b"\0" * (-len(self.bin) % 4)
        chunks = struct.pack("<I4s", len(descriptor), b"JSON") + descriptor
        chunks += struct.pack("<I4s", len(payload), b"BIN\0") + payload
        return struct.pack("<4sII", b"glTF", 2, 12 + len(chunks)) + chunks


def add_material(glb, material, cache):
    name = material.m_Name
    if name in cache:
        return cache[name]
    main = dict(material.m_SavedProperties.m_TexEnvs)["_MainTex"]
    texture = main.m_Texture.read()
    if texture.m_Name != "controller16" or (main.m_Scale.x, main.m_Scale.y, main.m_Offset.x, main.m_Offset.y) != (1, 1, 0, 0):
        raise ValueError(f"Unexpected texture mapping on {name}")
    if not glb.doc["images"]:
        image = io.BytesIO()
        # The OEM button shader outputs opaque alpha. The shell's rim pass
        # uses atlas alpha for gloss. Do not turn those values into cutouts.
        texture.image.convert("RGB").save(image, "PNG")
        glb.doc["images"].append({"name": texture.m_Name, "bufferView": glb.view(image.getvalue()), "mimeType": "image/png"})
        glb.doc["textures"].append({"source": 0})
    color = dict(material.m_SavedProperties.m_Colors)["_Color"]
    # Approximate the custom view-dependent rim with a standard glTF
    # material. The six meshes, UVs, neutral transforms and atlas are OEM.
    cache[name] = len(glb.doc["materials"])
    glb.doc["materials"].append({"name": name, "pbrMetallicRoughness": {
        "baseColorFactor": [color.r, color.g, color.b, 1.0], "baseColorTexture": {"index": 0},
        "roughnessFactor": 0.65, "metallicFactor": 0.0,
    }})
    return cache[name]


def extract(apk_path):
    with apk_path.open("rb") as fp:
        digest = hashlib.file_digest(fp, "sha256").hexdigest()
    if digest != SOURCE_SHA256:
        raise ValueError(f"Unverified VR Home build, SHA-256 {digest}")
    env = UnityPy.Environment()
    with zipfile.ZipFile(apk_path) as apk:
        for name in ("level1", "sharedassets1.assets"):
            env.load_file(io.BytesIO(read_asset(apk, name)), name=name)
    scene = env.files["level1"]
    root = scene.objects[1842].read()
    camera = scene.objects[984].read()
    if (root.m_GameObject.read().m_Name != "DefaultController"
            or root.m_Father.m_PathID != camera.m_Father.m_PathID
            or camera.m_Father.read().m_GameObject.read().m_Name != "HVRRightController"
            or camera.m_GameObject.read().m_Name != "EventCamera"
            or not np.allclose(local_matrix(camera), np.eye(4))):
        raise ValueError("Unexpected grip or aiming transform")
    children = {p.read().m_GameObject.read().m_Name: p.read() for p in root.m_Children}
    glb, materials = Glb(), {}
    info = {"apk_sha256": digest, "unity": scene.unity_version, "scene": "level1",
            "grip": "HVRRightController", "model_transform": 1842, "aim_camera_transform": 984,
            "unity_to_grip_gltf": "Bake DefaultController and child transforms, then reflect Z. Meters.",
            "visible_ray_origin_m": [0, 0.020, -0.069], "visible_ray_direction": [0, 0, -1],
            "model_matrix_unity": local_matrix(root).tolist(), "parts": []}
    reflection = np.diag([1, 1, -1, 1])
    for name in PARTS:
        transform = children[name]
        go = transform.m_GameObject.read()
        components = {k.component.deref().type.name: k.component for k in go.m_Component}
        mesh_ptr = components["MeshFilter"].read().m_Mesh
        mesh = mesh_ptr.read()
        renderer = components["MeshRenderer"].read()
        handler = MeshHandler(mesh)
        handler.process()
        matrix = reflection @ local_matrix(root) @ local_matrix(transform)
        linear = matrix[:3, :3]
        vertices = np.asarray(handler.m_Vertices) @ linear.T + matrix[:3, 3]
        normals = np.asarray(handler.m_Normals) @ np.linalg.inv(linear)
        normals /= np.linalg.norm(normals, axis=1, keepdims=True)
        uv = np.array(handler.m_UV0)
        uv[:, 1] = 1 - uv[:, 1]  # Unity origin lower-left, decoded PNG and glTF upper-left.
        faces, = handler.get_triangles()
        material_ptr, = renderer.m_Materials
        faces = np.asarray(faces, dtype=np.int32)[:, [0, 2, 1]]
        if faces.min() < 0 or faces.max() >= len(vertices) or faces.max() > 65535:
            raise ValueError(f"Invalid indices for {name}")
        triangle = vertices[faces]
        geometric = np.cross(triangle[:, 1] - triangle[:, 0], triangle[:, 2] - triangle[:, 0])
        if np.any((geometric * normals[faces].mean(axis=1)).sum(axis=1) <= 0):
            raise ValueError(f"Front-face winding disagrees with source normals on {name}")
        attr = {"POSITION": glb.accessor(vertices, 5126, "VEC3", 34962, bounds=True),
                "NORMAL": glb.accessor(normals, 5126, "VEC3", 34962),
                "TEXCOORD_0": glb.accessor(uv, 5126, "VEC2", 34962)}
        glb.doc["meshes"][0]["primitives"].append({
            "attributes": attr, "indices": glb.accessor(faces.ravel(), 5123, "SCALAR", 34963),
            "material": add_material(glb, material_ptr.read(), materials), "mode": 4, "extras": {"part": name},
        })
        info["parts"].append({"name": name, "mesh": mesh.m_Name, "mesh_path_id": mesh_ptr.m_PathID,
                              "material_path_id": material_ptr.m_PathID, "transform": transform.object_reader.path_id,
                              "vertices": len(vertices), "triangles": len(faces), "min_m": vertices.min(axis=0).tolist(),
                              "max_m": vertices.max(axis=0).tolist()})
    data = glb.encode()
    info.update(glb_sha256=hashlib.sha256(data).hexdigest(), glb_bytes=len(data))
    return data, info


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apk", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--evidence", type=Path, help="Optional JSON with source IDs, dimensions and hashes")
    args = parser.parse_args()
    data, info = extract(args.apk)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    if args.evidence:
        args.evidence.write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    print(f"{info['glb_sha256']}  {args.output} ({len(data)} bytes)")
