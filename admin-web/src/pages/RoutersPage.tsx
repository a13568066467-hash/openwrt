import { Table, Tag } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { adminApi } from '../api';
import PageShell from '../components/PageShell';

export default function RoutersPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['routers'],
    queryFn: () => adminApi.getRouters().then(r => r.data),
  });

  return (
    <PageShell title="设备管理">
      <Table
        loading={isLoading}
        dataSource={data}
        rowKey="id"
        pagination={{ pageSize: 10 }}
        columns={[
          { title: 'ID', dataIndex: 'id', width: 60 },
          { title: '设备ID', dataIndex: 'device_id' },
          { title: '名称', dataIndex: 'name' },
          {
            title: '状态',
            dataIndex: 'online',
            render: (online: boolean) => (
              <Tag color={online ? 'success' : 'default'}>{online ? '在线' : '离线'}</Tag>
            ),
          },
          { title: '最后心跳', dataIndex: 'last_heartbeat' },
        ]}
      />
    </PageShell>
  );
}
