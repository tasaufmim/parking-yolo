import React, { useState, useEffect, useCallback } from "react";
import { Table, Button, Modal, Form, Input, Switch, Space, Popconfirm, Tag, message } from "antd";
import { VideoCameraAddOutlined, EditOutlined, DeleteOutlined, LinkOutlined } from "@ant-design/icons";
import { getCameras, addCamera, updateCamera, deleteCamera, toggleCameraEnabled } from "../utils/api";

export default function CameraManager() {
  const [cameras, setCameras] = useState([]);
  const [maxCameras, setMaxCameras] = useState(6);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingCamera, setEditingCamera] = useState(null);
  const [form] = Form.useForm();

  const fetchCameras = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getCameras();
      setCameras(data.cameras || []);
      setMaxCameras(data.max_cameras || 6);
    } catch (e) {
      message.error("Failed to load cameras");
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchCameras();
  }, [fetchCameras]);

  const handleAdd = () => {
    setEditingCamera(null);
    form.resetFields();
    setModalVisible(true);
  };

  const handleEdit = (record) => {
    setEditingCamera(record);
    form.setFieldsValue({ name: record.name, rtsp_url: record.rtsp_url });
    setModalVisible(true);
  };

  const handleDelete = async (id) => {
    try {
      await deleteCamera(id);
      message.success("Camera deleted");
      fetchCameras();
    } catch (e) {
      message.error("Failed to delete: " + e.message);
    }
  };

  const handleToggle = async (id, checked) => {
    try {
      await toggleCameraEnabled(id, checked);
      message.success(checked ? "Camera enabled" : "Camera disabled");
      fetchCameras();
    } catch (e) {
      message.error("Failed to toggle: " + e.message);
    }
  };

  const handleModalOk = async () => {
    try {
      const values = await form.validateFields();
      if (editingCamera) {
        await updateCamera(editingCamera.id, values.name, values.rtsp_url);
        message.success("Camera updated");
      } else {
        await addCamera(values.name, values.rtsp_url);
        message.success("Camera added");
      }
      setModalVisible(false);
      fetchCameras();
    } catch (e) {
      if (!e.errorFields) message.error(e.message || "Operation failed");
    }
  };

  const columns = [
    {
      title: "Camera ID",
      dataIndex: "id",
      key: "id",
      width: 110,
      render: (val) => <Tag color="blue" style={{ fontFamily: "monospace", fontWeight: 600 }}>{val}</Tag>,
    },
    {
      title: "Name",
      dataIndex: "name",
      key: "name",
      width: 180,
    },
    {
      title: "RTSP URL",
      dataIndex: "rtsp_url",
      key: "rtsp_url",
      ellipsis: true,
      render: (val) => (
        <span style={{ fontFamily: "monospace", fontSize: 12, color: "#666" }}>
          {val}
        </span>
      ),
    },
    {
      title: "Enabled",
      dataIndex: "enabled",
      key: "enabled",
      width: 100,
      align: "center",
      render: (enabled, record) => (
        <Switch
          checked={enabled}
          onChange={(checked) => handleToggle(record.id, checked)}
        />
      ),
    },
    {
      title: "Status",
      key: "status",
      width: 100,
      align: "center",
      render: (_, record) => (
        <Tag color={record.enabled ? "green" : "default"}>
          {record.enabled ? "Active" : "Disabled"}
        </Tag>
      ),
    },
    {
      title: "Actions",
      key: "actions",
      width: 120,
      align: "center",
      render: (_, record) => (
        <Space size="small">
          <Button
            type="text"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
            size="small"
          />
          <Popconfirm
            title="Delete camera?"
            description="This action cannot be undone."
            onConfirm={() => handleDelete(record.id)}
            okText="Delete"
            okType="danger"
          >
            <Button type="text" danger icon={<DeleteOutlined />} size="small" />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div className="camera-manager">
      <div className="camera-manager-header">
        <div>
          <h2 className="camera-manager-title">
            <VideoCameraAddOutlined style={{ marginRight: 8 }} />
            Camera Manager
          </h2>
          <p className="camera-manager-subtitle">
            Manage up to {maxCameras} camera connections
          </p>
        </div>
        {cameras.length < maxCameras && (
          <Button type="primary" icon={<VideoCameraAddOutlined />} onClick={handleAdd}>
            Add Camera
          </Button>
        )}
      </div>

      {cameras.length === 0 ? (
        <div className="camera-manager-empty">
          <div className="empty-icon">
            <VideoCameraAddOutlined />
          </div>
          <h3>No cameras configured</h3>
          <p>Add your first camera to start monitoring parking slots</p>
          <Button type="primary" icon={<VideoCameraAddOutlined />} onClick={handleAdd}>
            Add Camera
          </Button>
        </div>
      ) : (
        <Table
          columns={columns}
          dataSource={cameras}
          rowKey="id"
          loading={loading}
          pagination={false}
          size="middle"
        />
      )}

      <Modal
        title={editingCamera ? "Edit Camera" : "Add Camera"}
        open={modalVisible}
        onOk={handleModalOk}
        onCancel={() => setModalVisible(false)}
        okText={editingCamera ? "Update" : "Add"}
        width={500}
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            name="name"
            label="Camera Name"
            rules={[{ required: true, message: "Please enter camera name" }]}
          >
            <Input placeholder="e.g. Entrance Gate, Zone A" />
          </Form.Item>
          <Form.Item
            name="rtsp_url"
            label="RTSP URL"
            rules={[{ required: true, message: "Please enter RTSP URL" }]}
          >
            <Input
              placeholder="rtsp://192.168.1.100:554/stream"
              style={{ fontFamily: "monospace" }}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}